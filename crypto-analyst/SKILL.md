---
name: crypto-analyst
description: >-
  Crypto Tokenomics & Market Structure Analyst. Generates Long-Term Spot reports (200 SMA,
  cycle drawdown, tokenomics dilution overhang, DCA zones) and Short-Term Futures reports
  (leverage, initial margin, liquidation buffers, 8h funding carry drag, scalp trade brackets).
argument-hint: "[spot-report <coin> | futures-report <symbol> --leverage <L> | check <coin> | funding <symbol>]"
---

# crypto-analyst

The Analyst differentiates between **Long-Term Spot Investment** and **Short-Term Leveraged Futures Trading**.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

### 1. Long-Term Spot Report
Evaluates macro cycle structure (200-day SMA, 50-day SMA, cycle drawdown) combined with tokenomics dilution overhang (MC/FDV ratio, unlock schedules) to recommend Dollar-Cost-Averaging (DCA) and macro swing levels.
```bash
# Long-Term Spot analysis on Bitcoin
python3 "${CLAUDE_SKILL_DIR}/analyst.py" spot-report bitcoin

# Long-Term Spot analysis on Solana (JSON format)
python3 "${CLAUDE_SKILL_DIR}/analyst.py" spot-report solana --json
```

### 2. Short-Term Futures Report & Trades
Calculates leverage risk parameters (isolated margin requirements, exact liquidation levels for LONG and SHORT), 8-hour funding rate carry drag, and generates immediate short-term scalp brackets (1h - 8h holding window).
```bash
# Short-Term Futures analysis on BTC with 5x leverage
python3 "${CLAUDE_SKILL_DIR}/analyst.py" futures-report BTCUSDT --leverage 5

# Short-Term Futures analysis on ETH with 10x leverage (Short-side bias)
python3 "${CLAUDE_SKILL_DIR}/analyst.py" futures-report ETHUSDT --leverage 10 --side short
```

### 3. Core Fundamental & Derivatives Checks
```bash
# Tokenomics & unlock overhang audit
python3 "${CLAUDE_SKILL_DIR}/analyst.py" check BTC

# Live perpetual funding rate & crowdedness
python3 "${CLAUDE_SKILL_DIR}/analyst.py" funding BTCUSDT
```
