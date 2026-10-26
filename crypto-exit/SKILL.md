---
name: crypto-exit
description: >-
  Crypto Exit Planner. Defines exact Stop-Loss and Take-Profit brackets before entering
  a position. Supports percentage stops, ATR-based dynamic volatility buffers, session lows,
  and multiple R targets (1R, 2R, 3R). Enforces spread/fee floor checks and holding window
  expiration. Writes crypto-trader/plan.json.
argument-hint: "[plan | show] [--stop pct:X|atr:K|price:P] [--target 2R|price:P] [--max-hold-hours H]"
---

# crypto-exit

The Exit Planner ensures you know exactly when to get out before risking capital.
In crypto, volatility regimes can shift rapidly; calculating stops using ATR or
explicit percentage floors prevents setting stops that are too tight to clear
exchange fee hurdles.

```bash
# Plan exit from the active crypto-trader/entry.json
python3 crypto-exit/exit.py plan --stop pct:2.0 --target 2R

# Use dynamic 14-bar ATR volatility stop
python3 crypto-exit/exit.py plan --symbol BTCUSDT --entry 80000 --stop atr:1.5 --target 2.5R

# Plan with fixed price coordinates
python3 crypto-exit/exit.py plan --symbol SOLUSDT --entry 180 --stop price:174.50 --target price:195.00

# View current active plan
python3 crypto-exit/exit.py show
```

Outputs:
- `crypto-trader/plan.json`
