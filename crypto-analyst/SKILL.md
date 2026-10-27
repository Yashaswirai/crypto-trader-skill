---
name: crypto-analyst
description: >-
  Crypto Tokenomics & Market Structure Analyst. Analyzes Market Cap vs Fully Diluted Valuation
  (FDV) dilution risk overhang, circulating supply ratio, volume turnover depth, and live
  perpetual funding rate sentiment. Standard library Python, zero API keys required.
argument-hint: "[check <coin> | funding <symbol>]"
---

# crypto-analyst

The Tokenomics & Market Structure Analyst provides fundamental analysis tailored for crypto.
While stock analysis focuses on quarterly 10-Q SEC reports, crypto fundamental edge comes from:
- **MC / FDV Overhang Ratio**: Evaluating whether heavy future token unlocks will dilute holders.
- **Liquidity Turnover**: Identifying whether token volume supports sizable position entries.
- **Funding Rates & Open Interest**: Evaluating whether price moves are spot-driven or leveraged perp squeezes.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
# Analyze tokenomics and dilution risk
python3 "${CLAUDE_SKILL_DIR}/analyst.py" check bitcoin

# Analyze Solana tokenomics
python3 "${CLAUDE_SKILL_DIR}/analyst.py" check solana

# Check live perpetual funding rate and market bias
python3 "${CLAUDE_SKILL_DIR}/analyst.py" funding BTCUSDT
```
