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

```bash
# View approved order ticket card
python3 crypto-broker/ticket.py show

# Execute simulated paper trade fill
python3 crypto-broker/ticket.py paper --confirm "yes"

# Inspect active positions and real-time live PnL
python3 crypto-broker/ticket.py positions

# Generate standard Binance REST / CCXT payload
python3 crypto-broker/ticket.py payload
```

Outputs:
- `crypto-trader/state/broker.json`
- `crypto-trader/portfolio.json`
