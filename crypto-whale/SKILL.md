---
name: crypto-whale
description: >-
  Crypto Whale & Smart Money Tracker. Tracks real-time large block orders, exchange tape
  flow, and institutional accumulation versus distribution on major liquid tokens.
  Calculates whale net delta (USD) without requiring any API keys.
argument-hint: "[scan <symbol> --min-usd USD | flow <symbol>]"
---

# crypto-whale

The Whale Tracker monitors institutional smart money order flow.
In crypto, retail traders often get trapped by sudden liquidity flushes; tracking whether
large block market takers (> $100,000) are accumulating into asks or distributing into
bids reveals true underlying market direction.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
# Scan recent whale block orders on BTC (> $100,000)
python3 "${CLAUDE_SKILL_DIR}/whale.py" scan BTCUSDT

# Scan Ethereum whale activity with $50k threshold
python3 "${CLAUDE_SKILL_DIR}/whale.py" scan ETHUSDT --min-usd 50000

# View net whale order flow
python3 "${CLAUDE_SKILL_DIR}/whale.py" flow SOLUSDT
```
