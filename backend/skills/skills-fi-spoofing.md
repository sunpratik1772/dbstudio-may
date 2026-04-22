# Skill: Fixed Income Spoofing

## Overview
Spoofing in Fixed Income involves placing large limit orders on one side of the order book with the intent to cancel them before execution, creating a false impression of supply/demand to manipulate prices. The spoofer profits by executing a smaller genuine order on the opposite side before cancelling the spoof orders.

## Regulatory Reference
- Dodd-Frank Section 747 — Spoofing Prohibition
- CEA Section 4c(a)(5)(C)
- MAR Article 12 — Market Manipulation
- CFTC Regulation 180.1
- FCA MAR 1 Annex 2

## Alert Trigger Fields
| Field      | Type   | Description                                  |
|------------|--------|----------------------------------------------|
| trader_id  | string | Suspected trader                             |
| book       | string | FI book (e.g., FI-RATES, FI-GOVT, FI-CREDIT)|
| alert_date | date   | Date of suspected activity                   |
| instrument | string | Bond/security identifier                     |
| cusip      | string | CUSIP identifier                             |
| alert_id   | string | Unique alert identifier                      |

## Required Data Extracts

### Extract 1: Order Flow (hs_client_order)
- **Purpose**: Identify large limit orders placed and then cancelled
- **Key fields**: order_id, trader_id, book, order_time, order_type, side, quantity, limit_price, status, venue
- **Focus**: LIMIT orders with CANCELLED status on same side

### Extract 2: Executions (hs_execution)
- **Purpose**: Identify the genuine execution opposite to the spoof orders
- **Key fields**: exec_id, trader_id, exec_time, side, exec_quantity, exec_price, venue, trade_version=1
- **HARD RULE**: Always include `trade_version:1`

### Extract 3: Communications (Oculus)
- **Keywords**: spoof, pull orders, layer, fake order, manipulate, depth, pull the bid, pull the offer, flood the book, step-out
- **Purpose**: Evidence of intent to create false market impression

### Extract 4: Market Data (EBS/Mercury)
- **Purpose**: Confirm price moved in direction of spoof before cancellation
- **Source**: EBS or Mercury tick data

## Signals to Create

### Signal 1: SPOOFING (built-in, mode=configure)
```json
{
  "mode": "configure",
  "signal_type": "SPOOFING",
  "params": {
    "cancel_ratio_threshold": 0.7,
    "window": "1d"
  }
}
```
- Flags when cancellation rate exceeds 70% of total limit orders

### Signal 2: ORDER_SIZE_ANOMALY (custom Python)
```python
# Spoof orders are typically much larger than genuine executions
if 'quantity' in df.columns and 'status' in df.columns:
    avg_exec = df[df['status'] == 'FILLED']['quantity'].mean() if (df['status'] == 'FILLED').any() else 1
    df['_size_ratio'] = df['quantity'] / avg_exec if avg_exec > 0 else 0
    df['_signal_flag'] = (df['_size_ratio'] > 5) & (df['status'] == 'CANCELLED')
    df['_signal_score'] = df['_size_ratio'].clip(0, 10).round(2)
    df['_signal_reason'] = df.apply(
        lambda r: f"Cancelled order {r['_size_ratio']:.1f}x larger than avg execution" if r['_signal_flag'] else "", axis=1
    )
else:
    df['_signal_flag'] = False
    df['_signal_score'] = 0.0
    df['_signal_reason'] = ''
df['_signal_type'] = 'ORDER_SIZE_ANOMALY'
df['_signal_window'] = '1d'
```

### Signal 3: RAPID_CANCEL_PATTERN (custom Python)
```python
# Spoof orders typically cancelled within seconds of placement
import pandas as pd
if 'order_time' in df.columns and 'status' in df.columns:
    df['order_time'] = pd.to_datetime(df['order_time'])
    df_sorted = df.sort_values('order_time')
    df_sorted['_next_time'] = df_sorted['order_time'].shift(-1)
    df_sorted['_life_secs'] = (df_sorted['_next_time'] - df_sorted['order_time']).dt.total_seconds().fillna(999)
    df = df_sorted
    df['_signal_flag'] = (df['_life_secs'] < 30) & (df['status'] == 'CANCELLED')
    df['_signal_score'] = (30 - df['_life_secs'].clip(0, 30)).clip(0, 10).round(2)
    df['_signal_reason'] = df.apply(
        lambda r: f"Order cancelled after {r['_life_secs']:.0f}s" if r['_signal_flag'] else "", axis=1
    )
else:
    df['_signal_flag'] = False
    df['_signal_score'] = 0.0
    df['_signal_reason'] = ''
df['_signal_type'] = 'RAPID_CANCEL'
df['_signal_window'] = '30s'
```

## Highlight Rules
| Condition                     | Colour    | Label             |
|-------------------------------|-----------|-------------------|
| `_signal_flag == True`        | `#FF4444` | SPOOF SIGNAL      |
| `status == 'CANCELLED'`       | `#FFD700` | CANCELLED         |
| `_keyword_hit == True`        | `#FF8C00` | COMM ALERT        |
| `order_type == 'LIMIT'`       | `#DDA0DD` | LIMIT ORDER       |

## Decision Thresholds
- **ESCALATE**: flag_count >= 5
- **REVIEW**: flag_count >= 2
- **DISMISS**: flag_count <= 1

## Report Sections
1. **order_analysis** — cancel ratio, order size distribution, order lifecycle
2. **execution_analysis** — genuine trades executed opposite to spoof side
3. **comms_analysis** — spoofing vocabulary in communications
4. **market_analysis** — price movement during spoof episode

## Investigation SOP
1. Calculate cancel ratio = cancelled_orders / total_limit_orders
2. Map order sequence: large limit orders placed → price moves → orders cancelled → genuine exec on opposite side
3. Measure time from order placement to cancellation (spoof orders typically < 30 seconds)
4. Compare spoof order size to average genuine execution size
5. Check for repeating pattern across the day (episodic spoofing)
6. Correlate communications with spoofing episodes
7. Review market impact: did price move in direction of spoof before cancellation?

## Copilot Instruction Example
> "Create an FI Spoofing workflow for {trader_id} in {book}.
> Add 3 signals: cancel rate detection, order size anomaly, and rapid cancel pattern.
> Add critic loop with 3 iterations."
