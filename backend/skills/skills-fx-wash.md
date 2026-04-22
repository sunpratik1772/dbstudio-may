# Skill: FX Wash Trading

## Overview
FX Wash Trading involves buying and selling the same currency pair in substantially equal quantities between related or coordinated accounts, creating artificial trading volume without genuine change in beneficial ownership. Used to inflate volumes, manipulate benchmarks, or generate fictitious P&L.

## Regulatory Reference
- CEA Section 4c(a) — Wash Sales
- MAR Article 12(1)(a) — Market Manipulation
- CFTC Regulation 180.1 / 180.2
- FCA COBS 2.1 — Market Integrity

## Alert Trigger Fields
| Field         | Type   | Description                               |
|---------------|--------|-------------------------------------------|
| trader_id     | string | Suspected trader identifier               |
| book          | string | FX book (e.g., FX-SPOT, FX-FWD)          |
| alert_date    | date   | Date of suspected activity                |
| currency_pair | string | e.g., EUR/USD, USD/JPY                    |
| entity        | string | Legal entity (for cross-entity detection) |
| alert_id      | string | Unique alert identifier                   |

## Required Data Extracts

### Extract 1: Client Orders (hs_client_order)
- **Purpose**: Identify order flow patterns showing balanced buy/sell activity
- **Key fields**: order_id, trader_id, book, currency_pair, order_time, side, quantity, status, venue, counterparty
- **Filter**: trader_id + book + date range

### Extract 2: Executions (hs_execution)
- **Purpose**: Match buy and sell executions across related accounts
- **Key fields**: exec_id, trader_id, exec_time, side, exec_quantity, exec_price, counterparty, notional_usd, trade_version=1
- **HARD RULE**: Always include `trade_version:1`
- **Note**: Loop over books if cross-book activity suspected

### Extract 3: Communications (Oculus)
- **Keywords**: wash, offset, back-to-back, round-trip, artificial volume, related account, step-out, rotate, coordinated
- **Purpose**: Evidence of pre-arrangement between counterparties

### Extract 4: Market Data (EBS/Reuters)
- **Purpose**: Validate that trades did not move market — confirming artificial nature
- **Source**: EBS or Reuters tick data

## Signals to Create

### Signal 1: WASH_TRADE (built-in, mode=configure)
```json
{
  "mode": "configure",
  "signal_type": "WASH_TRADE",
  "params": {
    "window_minutes": 10,
    "ratio_threshold": 0.8
  }
}
```
- Flags when buy/sell quantity ratio exceeds 80% (near-perfect offset)

### Signal 2: COUNTERPARTY_CIRCULARITY (custom Python)
```python
# Detect where trader appears as both buyer and counterparty
if 'counterparty' in df.columns and 'trader_id' in df.columns:
    related = df['counterparty'].isin(['INTERNAL', 'RELATED', df['trader_id'].iloc[0]])
    df['_signal_flag'] = related
    df['_signal_score'] = related.astype(float) * 10
    df['_signal_reason'] = df.apply(
        lambda r: f"Trade with related/internal counterparty: {r['counterparty']}" if r['_signal_flag'] else "", axis=1
    )
else:
    df['_signal_flag'] = False
    df['_signal_score'] = 0.0
    df['_signal_reason'] = ''
df['_signal_type'] = 'COUNTERPARTY_CIRCULARITY'
df['_signal_window'] = '1d'
```

### Signal 3: PRICE_NEUTRALITY (custom Python)
```python
# Wash trades typically have near-zero net P&L
if 'signed_notional' in df.columns:
    net_notional = df['signed_notional'].sum()
    total_notional = df['signed_notional'].abs().sum()
    neutrality = 1 - (abs(net_notional) / total_notional) if total_notional > 0 else 0
    df['_signal_flag'] = neutrality > 0.9
    df['_signal_score'] = round(neutrality * 10, 2)
    df['_signal_reason'] = f"Net notional neutrality: {neutrality:.2%}" if df['_signal_flag'].any() else ''
else:
    df['_signal_flag'] = False
    df['_signal_score'] = 0.0
    df['_signal_reason'] = ''
df['_signal_type'] = 'PRICE_NEUTRALITY'
df['_signal_window'] = '1d'
```

## Highlight Rules
| Condition                   | Colour    | Label              |
|-----------------------------|-----------|--------------------|
| `_signal_flag == True`      | `#FF4444` | WASH SIGNAL        |
| `_keyword_hit == True`      | `#FF8C00` | COMM ALERT         |
| `side == 'BUY'`             | `#90EE90` | BUY                |
| `side == 'SELL'`            | `#87CEEB` | SELL               |
| `status == 'CANCELLED'`     | `#FFD700` | CANCELLED          |

## Decision Thresholds
- **ESCALATE**: flag_count >= 3
- **REVIEW**: flag_count >= 1
- **DISMISS**: flag_count == 0

## Report Sections
1. **execution_analysis** — buy/sell ratio, net notional, counterparty breakdown
2. **comms_analysis** — keyword hits, coordination evidence
3. **counterparty_analysis** — related entity mapping

## Investigation SOP
1. Map all counterparties: identify related entities, internal desks, affiliated funds
2. Calculate net position change — wash trades leave near-zero net
3. Measure price impact — wash trades should not move market
4. Verify beneficial ownership — was ownership actually transferred?
5. Cross-reference with other desks/books for coordinated activity
6. Check time clustering — wash trades often executed within seconds of each other
7. Escalate if counterparty is internal/related AND buy/sell ratio > 80%

## Copilot Instruction Example
> "Create an FX Wash Trade workflow for {trader_id} in {currency_pair}.
> Use 3 signals: wash trade ratio, counterparty circularity, and price neutrality.
> Loop over FX-SPOT and FX-FWD books."
