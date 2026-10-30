---
name: crypto-budget
description: >-
  Crypto Position Sizer. Calculates spot cash allocations (1x leverage, zero liquidation risk)
  and leveraged futures positions (2x-20x leverage, initial margin, exact liquidation price,
  safety buffer enforcement). Formats bracket orders into crypto-trader/orders.json.
argument-hint: "[--budget USD] [--max-loss USD] [--limit PRICE] [--leverage 1|2|5|10]"
---

# crypto-budget

The Position Sizer dynamically sizes trades depending on whether you are trading Spot or Futures.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

### 1. Spot Trading (Long-Term 1x Asset Allocation)
Sizes whole and fractional tokens matching exchange `LOT_SIZE` filters with **zero liquidation risk**:
```bash
# Size spot trade risking max $100 on $10,000 budget
python3 "${CLAUDE_SKILL_DIR}/size.py" --budget 10000 --max-loss 100 --write
```

### 2. Futures Trading (Short-Term Leveraged Sizing)
Calculates required initial margin, exact liquidation price, and enforces that your Stop-Loss triggers well before liquidation:
```bash
# Size 5x perpetual futures contract
python3 "${CLAUDE_SKILL_DIR}/size.py" --budget 5000 --max-loss 50 --leverage 5 --write
```

Outputs:
- `crypto-trader/orders.json`
