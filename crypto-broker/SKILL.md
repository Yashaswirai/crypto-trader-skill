---
name: crypto-broker
description: >-
  Crypto Order Executor & Paper Trading Simulator. Formats verified trade tickets, verifies
  PASS fingerprints from crypto-risk, and executes paper simulations with real-time mark-to-market
  PnL tracking. Formats Binance OCO and CCXT REST payloads for optional live dispatch.
argument-hint: "[show | paper --confirm 'yes' | positions | payload]"
---

# crypto-broker

The Broker handles order presentation and execution simulation.
It prioritizes safety above all else:
- Paper trading is active by default.
- It refuses to display any order unless `crypto-risk` has signed an identical PASS verdict.
- It requires word-for-word human approval (`--confirm 'yes'`) before executing.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

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

Outputs:
- `crypto-trader/state/broker.json`
- `crypto-trader/portfolio.json`
