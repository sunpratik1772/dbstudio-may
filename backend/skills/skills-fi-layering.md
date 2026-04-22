# Skill: Fixed Income Layering

## Overview
Layering is a form of market manipulation closely related to spoofing — multiple limit orders are placed in rapid succession on one side of the order book at progressively better prices, creating an artificial appearance of deep market interest (false depth). Once the genuine trade executes on the opposite side, all the layered orders are cancelled. Unlike spoofing (single large order), layering uses many stacked orders.

## Regulatory Reference
- Dodd-Frank Section 747
- MAR Article 12(2)(b) — Transactions that secure a dominant position
- FCA Final Notice — Navinder Sarao (2016) — benchmark layering case
- CFTC Advisory 12-38

## Alert Trigger Fields
| Field      | Type   | Description                                  |
|------------|--------|----------------------------------------------|
| trader_id  | string | Suspected trader                             |
| book       | string | FI book (e.g., FI-RATES, FI-FUTURES)        |
| alert_date | date   | Date of suspected activity                   |
| instrument | string | Bond/future identifier                       |
| cusip      | string | CUSIP / contract identifier                  |
| desk       | string | Trading desk                                 |
| alert_id   | string | Unique alert identifier                      |

## Required Data Extracts

### Extract 1: Order Book Snapshots (hs_client_order)
- **Purpose**: Identify cascading limit orders placed in layers on one side
- **Key fields**: order_id, trader_id, order_time, order_type, side, quantity, limit_price, status, venue, seq_no
- **Sort by**: limit_price (to show stacking)
- **Focus**: LIMIT orders, same side, narrow price range, rapid placement

### Extract 2: Executions (hs_execution)
- **Purpose**: Identify the genuine execution that occurs while layers are present
- **Key fields**: exec_id, trader_id, exec_time, side, exec_quantity, exec_price, trade_version=1
- **HARD RULE**: Always include `trade_version:1`

### Extract 3: Communications (Oculus)
- **Keywords**: layer, stack, depth, flood, artificial, pull, book manipulation, step-on, create interest, fake depth
- **Purpose**: Evidence of intent to create artificial market depth

### Extract 4: Market Data (EBS/Mercury)
- **Purpose**: Validate order book depth changes matching the layer placement and cancellation
- **Source**: Mercury preferred (order book depth data)

## Signals to Create

### Signal 1: LAYERING (built-in, mode=configure)
```json
{
  "mode": "configure",
  "signal_type": "LAYERING",
  "params": {
    "min_layers": 5,
    "window": "30m"
  }
}
```
- Flags when 5+ limit orders appear on one side with significant imbalance vs. opposite side

### Signal 2: CASCADING_PRICE_LEVELS (custom Python)
```python
# Detect multiple limit orders at progressively better prices on same side
import pandas as pd
if all(c in df.columns for c in ['order_type', 'side', 'limit_price', 'order_time']):
    df['order_time'] = pd.to_datetime(df['order_time'])
    df = df.sort_values('order_time')
    limit_orders = df[df['order_type'] == 'LIMIT'].copy()
    for side in ['BUY', 'SELL']:
        side_df = limit_orders[limit_orders['side'] == side].copy()
        if len(side_df) >= 3:
            side_df = side_df.sort_values('limit_price', ascending=(side == 'BUY'))
            price_steps = side_df['limit_price'].diff().abs()
            is_cascading = (price_steps < 0.005).all() and len(side_df) >= 3
            df.loc[df['side'] == side, '_signal_flag'] = is_cascading
            df.loc[df['side'] == side, '_signal_score'] = min(len(side_df) / 3, 10)
            df.loc[df['side'] == side, '_signal_reason'] = (
                f"{len(side_df)} cascading {side} limit orders in narrow price range" if is_cascading else ""
            )
if '_signal_flag' not in df.columns:
    df['_signal_flag'] = False
    df['_signal_score'] = 0.0
    df['_signal_reason'] = ''
df['_signal_type'] = 'CASCADING_PRICE_LEVELS'
df['_signal_window'] = '30m'
```

### Signal 3: LAYER_CANCEL_SEQUENCE (custom Python)
```python
# Detect pattern: burst of limit orders → genuine exec → mass cancellation
import pandas as pd
if all(c in df.columns for c in ['order_type', 'status', 'order_time']):
    df['order_time'] = pd.to_datetime(df['order_time'])
    df_sorted = df.sort_values('order_time').reset_index(drop=True)
    # Window: count how many orders are placed and then cancelled within 60s
    df_sorted['_rolling_cancels'] = (
        df_sorted['status'].eq('CANCELLED')
        .rolling(window=10, min_periods=1)
        .sum()
    )
    df = df_sorted
    df['_signal_flag'] = df['_rolling_cancels'] >= 5
    df['_signal_score'] = (df['_rolling_cancels'] / 5).clip(0, 10).round(2)
    df['_signal_reason'] = df.apply(
        lambda r: f"{int(r['_rolling_cancels'])} cancels in rolling 10-order window" if r['_signal_flag'] else "", axis=1
    )
else:
    df['_signal_flag'] = False
    df['_signal_score'] = 0.0
    df['_signal_reason'] = ''
df['_signal_type'] = 'LAYER_CANCEL_SEQUENCE'
df['_signal_window'] = '60s'
```

## Highlight Rules
| Condition                      | Colour    | Label               |
|--------------------------------|-----------|---------------------|
| `_signal_flag == True`         | `#FF4444` | LAYER SIGNAL        |
| `status == 'CANCELLED'`        | `#FFD700` | CANCELLED           |
| `order_type == 'LIMIT'`        | `#DDA0DD` | LIMIT (Layer)       |
| `_keyword_hit == True`         | `#FF8C00` | COMM ALERT          |

## Decision Thresholds
- **ESCALATE**: flag_count >= 8
- **REVIEW**: flag_count >= 3
- **DISMISS**: flag_count < 3

## Report Sections
1. **order_analysis** — layer count, price step analysis, cancel sequence timing
2. **execution_analysis** — genuine executions during layer episodes
3. **comms_analysis** — coordination language, references to depth/book manipulation
4. **market_analysis** — order book depth changes matching layer pattern

## Normalise & Enrich Config
```json
{
  "track_lifecycle": true,
  "compute_signed_notional": true,
  "field_renames": {}
}
```
Track lifecycle is important for layering — need to see PENDING → CANCELLED transitions.

## Investigation SOP
1. Build a time-sequenced order book view sorted by (order_time, limit_price)
2. Identify episodes: burst of LIMIT orders on same side within 60-second window
3. Measure order book imbalance: buy limit qty vs. sell limit qty
4. Find the genuine execution that occurs while layers are present
5. Confirm mass cancellation after genuine execution
6. Calculate price impact: did layered side push price toward genuine trade?
7. Check for repeat episodes across the day (serial layering)
8. Cross-reference comms for language about "creating interest" or "false depth"
9. Compare to historical order-to-cancel ratio baseline for this trader

## Copilot Instruction Example
> "Create an FI Layering workflow for {trader_id} in {book} {instrument}.
> Use 3 signals: layering imbalance, cascading price levels, layer-cancel sequence.
> Enable lifecycle tracking, add comms highlighting, generate Excel with 5 tabs."
