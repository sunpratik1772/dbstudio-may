# Skill: FX Front-Running (FRO)

## Overview
FX Front-Running occurs when a trader executes proprietary trades ahead of a pending client order, profiting from the anticipated price impact when the larger client order hits the market. This includes trading ahead of a WM/Reuters fix print.

## Regulatory Reference
- MAR Article 8 — Market Manipulation / Insider Dealing
- FCA PS 16/20 — FX Global Code of Conduct
- CFTC Regulation 180.1

## Alert Trigger Fields
| Field         | Type   | Description                             |
|---------------|--------|-----------------------------------------|
| trader_id     | string | Suspected trader identifier             |
| book          | string | FX spot/forward book (e.g., FX-SPOT)   |
| alert_date    | date   | Date of suspected activity (YYYY-MM-DD) |
| currency_pair | string | e.g., EUR/USD, USD/JPY, GBP/USD        |
| alert_id      | string | Unique alert identifier                 |

## Required Data Extracts

### Extract 1: Client Orders (hs_client_order)
- **Purpose**: Identify large client orders that may have been front-run
- **Key fields**: order_id, trader_id, book, currency_pair, order_time, order_type, side, quantity, limit_price, status, venue
- **Filter**: trader_id + book + date range

### Extract 2: Proprietary Executions (hs_execution)
- **Purpose**: Identify prop trades placed ahead of client orders on same side
- **Key fields**: exec_id, order_id, trader_id, exec_time, side, exec_quantity, exec_price, venue, trade_version=1, counterparty, notional_usd
- **HARD RULE**: Always include `trade_version:1` — never from context

### Extract 3: Communications (Oculus)
- **Purpose**: Corroborating evidence of intent and coordination
- **Key fields**: user, timestamp, display_post, event_type
- **Keywords**: fix, benchmark, front-run, ahead, before the move, WM fix, cover, rotate, push through, client order, step-out, pull

### Extract 4: Market Data (EBS)
- **Purpose**: Confirm price direction and magnitude after client execution
- **Source**: EBS tick data
- **Key fields**: timestamp, symbol, bid, ask, mid, spread_pips, bid_size, ask_size

## Signals to Create

### Signal 1: FRONT_RUNNING (built-in, mode=configure)
```json
{
  "mode": "configure",
  "signal_type": "FRONT_RUNNING",
  "params": {
    "window_minutes": 5,
    "price_move_threshold": 0.0003
  }
}
```
- Flags executions where price moves > 3 pips within 5-minute window

### Signal 2: TIMING_CORRELATION (custom Python)
```python
# Compute time delta between prop exec and client order on same side
# Flag if delta < 3 minutes (prop came before client)
df['_time_delta_mins'] = (
    pd.to_datetime(df['exec_time']) - pd.to_datetime(df['order_time'])
).dt.total_seconds() / 60
df['_signal_flag'] = df['_time_delta_mins'].abs() < 3
df['_signal_score'] = (3 - df['_time_delta_mins'].clip(0, 3)).clip(0, 10).round(2)
df['_signal_reason'] = df.apply(
    lambda r: f"Prop trade {abs(r['_time_delta_mins']):.1f}m before client order" if r['_signal_flag'] else "", axis=1
)
df['_signal_type'] = 'TIMING_CORRELATION'
df['_signal_window'] = '3m'
```

### Signal 3: COMM_KEYWORD_DENSITY (context-based)
- Derived from `comms_data._keyword_hit` count
- Flag if comm_keyword_hits > 3 within surveillance window
- Use DECISION_RULE `flag_count_expr`: `flag_count > 0`

## Highlight Rules
| Condition                   | Colour    | Label          |
|-----------------------------|-----------|----------------|
| `_signal_flag == True`      | `#FF4444` | FRO SIGNAL     |
| `_keyword_hit == True`      | `#FF8C00` | COMM ALERT     |
| `side == 'BUY'`             | `#90EE90` | BUY            |
| `side == 'SELL'`            | `#87CEEB` | SELL           |

## Decision Thresholds
- **ESCALATE**: flag_count >= 5
- **REVIEW**: flag_count >= 1
- **DISMISS**: flag_count == 0

## Report Sections
1. **trade_analysis** — aggregate executions, signed_notional, venue breakdown
2. **comms_analysis** — keyword hit count, communication timeline, event types
3. **market_analysis** — price move magnitude before/after execution

## Report Tabs
- Client Orders, Executions (highlighted), Signals (highlighted), Communications (highlighted), Market Data (EBS)

## Investigation SOP
1. Check if trader had visibility of client order (RFS/RFQ log, sales call) before executing prop
2. Review time sequence: prop trade → client order entry → client execution → price move
3. Measure price impact of client order vs. prop P&L
4. Look for pattern across multiple client orders on same day
5. Cross-reference communications for fix references or "get ahead" language
6. Escalate to Senior Surveillance if flag_count >= 5 or explicit WM Fix references in comms
7. Preserve audit trail: resolved_query + execution timestamps

## Copilot Instruction Example
> "Create an FX FRO workflow for trader {trader_id} in EUR/USD on {alert_date}.
> Add 3 signals: price move detection, timing correlation, and comms keyword density.
> Add a critic loop that verifies 3 times before closing the alert."
