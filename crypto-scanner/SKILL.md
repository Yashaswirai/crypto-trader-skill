---
name: crypto-scanner
description: >-
  Crypto Market Scanner. Scans thousands of 24/7 crypto pairs across liquid USDT markets
  for high-probability setups: Spot Swing consolidations, Futures Long momentum surges,
  Futures Short breakdowns, 24h breakouts, and session range breakouts.
argument-hint: "[spot | futures | universe | daily | session]"
---

# crypto-scanner

The Crypto Scanner discovers trading candidates customized for your trading horizon:

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

### 1. Spot Trading (Long-Term Macro Swings)
Scans for tokens in tight multi-day consolidation bases with healthy liquidity and zero liquidation risk:
```bash
python3 "${CLAUDE_SKILL_DIR}/scan.py" spot
```

### 2. Futures Trading (Short-Term Momentum & Breakdowns)
Scans for rapid intraday momentum surges (LONG) and flush continuation dumps (SHORT):
```bash
python3 "${CLAUDE_SKILL_DIR}/scan.py" futures
```

### 3. General Daily & Session Breakouts
```bash
# Discover top liquid USDT crypto pairs
python3 "${CLAUDE_SKILL_DIR}/scan.py" universe --min-volume 10000000

# Run 24-hour setup scan (breakouts, flags, surges)
python3 "${CLAUDE_SKILL_DIR}/scan.py" daily

# Scan for London session range breakouts from the Asian range
python3 "${CLAUDE_SKILL_DIR}/scan.py" session --session london
```

Outputs:
- `crypto-trader/universe.txt`
- `crypto-trader/watchlist.json`
