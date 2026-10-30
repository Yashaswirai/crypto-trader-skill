---
name: crypto-broker
description: >-
  Crypto Order Executor & Broker Simulator. Formats differentiated Spot (Long-Term) and
  Futures (Short-Term) trade tickets, verifies PASS fingerprints from crypto-risk, and executes
  simulations or live dispatch for ZebPay Spot & Futures.
argument-hint: "[show | paper --confirm 'yes' | positions | payload | dispatch-zebpay]"
---

# crypto-broker

The Broker handles order presentation, simulation, and live dispatch for both Spot and Futures.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

### 1. Spot vs Futures Ticket Inspection
Automatically detects whether an order is Spot or Futures:
- **Spot Ticket**: Displays cash allocation, long-term horizon, and confirms zero liquidation risk.
- **Futures Ticket**: Displays initial margin, leverage multiplier, exact liquidation level, and short-term holding window.
```bash
# View approved order ticket card
python3 "${CLAUDE_SKILL_DIR}/ticket.py" show
```

### 2. Paper Trading Execution
```bash
# Execute simulated paper trade fill
python3 "${CLAUDE_SKILL_DIR}/ticket.py" paper --confirm "yes"

# Inspect active positions and mark-to-market PnL
python3 "${CLAUDE_SKILL_DIR}/ticket.py" positions
```

### 3. ZebPay Live Dispatcher (Spot & Futures)
Supports both ZebPay Spot (`https://sapi.zebpay.com`) and ZebPay Futures (`https://futuresbe.zebpay.com`):
```bash
# Preview ZebPay Spot order
python3 "${CLAUDE_SKILL_DIR}/zebpay_dispatcher.py" preview --market spot --quote INR

# Preview ZebPay Futures order
python3 "${CLAUDE_SKILL_DIR}/zebpay_dispatcher.py" preview --market futures --quote INR

# Live dispatch with explicit confirmation
python3 "${CLAUDE_SKILL_DIR}/ticket.py" dispatch-zebpay --confirm "yes" --quote INR
```

Outputs:
- `crypto-trader/state/broker.json`
- `crypto-trader/portfolio.json`
