---
name: crypto-broker
description: >-
  Crypto Order Executor & Paper Trading Simulator. Formats verified trade tickets, verifies
  PASS fingerprints from crypto-risk, and executes paper simulations with real-time mark-to-market
  PnL tracking. Formats Binance OCO and CCXT REST payloads for optional live dispatch, plus
  automated live execution dispatch for ZebPay.
argument-hint: "[show | paper --confirm 'yes' | positions | payload | dispatch-zebpay]"
---

# crypto-broker

The Broker handles order presentation, simulation, and live dispatch.
It prioritizes safety above all else:
- Paper trading is active by default.
- It refuses to display or dispatch any order unless `crypto-risk` has signed an identical PASS verdict.
- It requires word-for-word human approval (`--confirm 'yes'`) before executing.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

### 1. Paper Trading & Ticket Inspection
```bash
# View approved order ticket card
python3 "${CLAUDE_SKILL_DIR}/ticket.py" show

# Execute simulated paper trade fill
python3 "${CLAUDE_SKILL_DIR}/ticket.py" paper --confirm "yes"

# Inspect active positions and real-time live PnL
python3 "${CLAUDE_SKILL_DIR}/ticket.py" positions

# Generate standard Binance REST / CCXT payload
python3 "${CLAUDE_SKILL_DIR}/ticket.py" payload
```

### 2. ZebPay Automated Live Dispatcher
Directly connects verified orders to the [ZebPay Spot REST API](https://docs.zebpay.com) (`https://sapi.zebpay.com`).

Set your credentials in environment variables (never in chat or git):
```bash
export ZEBPAY_API_KEY="your_api_key"
export ZEBPAY_API_SECRET="your_secret_key"
# Or alternatively for JWT authentication:
# export ZEBPAY_JWT_TOKEN="your_jwt_bearer_token"
```

Commands:
```bash
# Preview mapped ZebPay payload (INR or USDT pairs)
python3 "${CLAUDE_SKILL_DIR}/zebpay_dispatcher.py" preview --quote INR

# Validate authentication signature and payload without submitting an order
python3 "${CLAUDE_SKILL_DIR}/ticket.py" dispatch-zebpay --dry-run --quote INR

# Execute live order on ZebPay with explicit confirmation
python3 "${CLAUDE_SKILL_DIR}/ticket.py" dispatch-zebpay --confirm "yes" --quote INR
```

Outputs:
- `crypto-trader/state/broker.json`
- `crypto-trader/portfolio.json`
