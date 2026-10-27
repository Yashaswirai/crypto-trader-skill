---
name: crypto-entry
description: >-
  Crypto Entry Timer. Watches crypto setups bar-by-bar (1m, 5m, 15m Binance k-lines)
  and identifies exact entry triggers when a completed bar CLOSES above a breakout level
  or session range high, with optional volume confirmation. Writes crypto-trader/entry.json
  for downstream exit planning. Standard library Python, zero API keys required.
argument-hint: "[check <symbol> | watchlist] [--setup breakout|session_orb] [--level PRICE] [--interval 1m|5m|15m]"
---

# crypto-entry

The Crypto Entry Timer watches price action bar by bar.
It enforces strict confirmation: an entry triggers only on a completed bar CLOSE
(never on mid-bar wicks that frequently produce fakeouts in crypto).

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
# Check if BTC has closed above resistance level
python3 "${CLAUDE_SKILL_DIR}/entry.py" check BTCUSDT --level 80500

# Check 5-minute bar with 1.5x volume surge requirement
python3 "${CLAUDE_SKILL_DIR}/entry.py" check SOLUSDT --level 185.00 --interval 5m --min-volume-x 1.5

# Check session range breakout
python3 "${CLAUDE_SKILL_DIR}/entry.py" check ETHUSDT --setup session_orb --interval 15m

# Check all candidates in active watchlist
python3 "${CLAUDE_SKILL_DIR}/entry.py" watchlist
```

Outputs:
- `crypto-trader/entry.json`
