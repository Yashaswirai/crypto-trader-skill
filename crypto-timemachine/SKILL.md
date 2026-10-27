---
name: crypto-timemachine
description: >-
  Crypto Time Machine. Replays 10,000 Monte Carlo bootstrap future paths using the token's
  recent historical 5-minute candle return distribution to calculate exact odds of hitting
  Take-Profit vs Stop-Loss before risking capital. Prints win/loss probabilities, mathematical
  expectancy (in R), and an honest statistical verdict.
argument-hint: "[run] [--simulations 10000] [--plan FILE]"
---

# crypto-timemachine

The Time Machine evaluates statistical edge before placing a trade.
Instead of relying on gut feel, it samples the token's actual recent volatility
and 5-minute return distribution across 10,000 simulated sessions to see how
frequently the target is reached before the stop loss.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
# Replay active plan in crypto-trader/plan.json
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run

# Replay with 20,000 simulations
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run --simulations 20000

# Replay arbitrary coordinates
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run --symbol ETHUSDT --entry 3200 --stop 3140 --target 3320
```
