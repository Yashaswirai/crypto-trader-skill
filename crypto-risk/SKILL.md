---
name: crypto-risk
description: >-
  Crypto Pre-Trade Risk Guardian. Validates proposed orders in crypto-trader/orders.json
  against safety limits: max loss per trade, cumulative daily loss, minimum R:R, maximum
  allowed leverage, daily trade frequency, and blocked coin lists. Records PASS/BLOCK
  verdicts to crypto-trader/state/risk.json.
argument-hint: "[--orders FILE] [--config FILE] [--no-write]"
---

# crypto-risk

The Risk Guardian acts as a firewall preventing impulsive trades and catastrophic losses.
Every trade must be checked and receive an explicit PASS verdict before the execution
broker can display an active order ticket.

```bash
# Check current proposed order
python3 crypto-risk/check.py

# Perform dry-run check without updating state
python3 crypto-risk/check.py --no-write

# Output structured JSON verdict
python3 crypto-risk/check.py --json
```

Outputs:
- `crypto-trader/state/risk.json`
