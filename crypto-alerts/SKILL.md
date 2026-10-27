---
name: crypto-alerts
description: >-
  Crypto Price & Session Alerts. Monitors trade plan stop losses, take profits, and max
  holding time windows. Provides countdowns to global crypto session opens (Asian, London,
  New York) and 8-hour funding rate settlement intervals. Caches quotes in crypto-trader/prices.json.
argument-hint: "[plan | check <symbol> | alert <symbol> --above/--below PRICE | funding | sessions]"
---

# crypto-alerts

The Crypto Alerts Monitor keeps track of price levels and key market clocks.
Because crypto is 24/7 without a traditional opening bell, it tracks the global
volatility windows that replace it:
- Active trade stops, targets, and time limits
- Asian, London, and New York market opens
- 8-hour perpetual funding rate settlement boundaries (00:00, 08:00, 16:00 UTC)

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
# Check status of active trade plan
python3 "${CLAUDE_SKILL_DIR}/alerts.py" plan

# Get real-time price & update cache
python3 "${CLAUDE_SKILL_DIR}/alerts.py" check BTCUSDT

# Price threshold alert
python3 "${CLAUDE_SKILL_DIR}/alerts.py" alert ETHUSDT --above 3300.00

# View countdown to next funding rate settlement
python3 "${CLAUDE_SKILL_DIR}/alerts.py" funding

# View global trading session clocks
python3 "${CLAUDE_SKILL_DIR}/alerts.py" sessions
```

Outputs:
- `crypto-trader/prices.json`
