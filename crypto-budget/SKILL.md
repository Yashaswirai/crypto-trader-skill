---
name: crypto-budget
description: >-
  Crypto Position Sizer. Calculates whole and fractional crypto position sizes (BTC, ETH,
  SOL, altcoins) matching exchange LOT_SIZE step filters. Sizes to the strictest of 4 limits:
  max loss per trade, position cap %, max order USD, and cash buffer. Formats bracket
  orders into crypto-trader/orders.json. Standard library Python, no network.
argument-hint: "[--budget USD] [--max-loss USD] [--limit PRICE] [--leverage 1|2|5]"
---

# crypto-budget

The Crypto Position Sizer prevents taking excessive risk on any individual trade.
In crypto, where assets can fluctuate dramatically, the sizer rounds fractional quantities
down to safe exchange step-sizes (e.g. 0.0001 BTC or 0.01 SOL) and ensures that the loss
at your stop never exceeds your authorized threshold.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
# Size trade from active plan
python3 "${CLAUDE_SKILL_DIR}/size.py"

# Specify customized budget and max loss
python3 "${CLAUDE_SKILL_DIR}/size.py" --budget 10000 --max-loss 100

# Size a limit order bracket
python3 "${CLAUDE_SKILL_DIR}/size.py" --limit 80100 --write

# Size a 2x leverage perpetual contract
python3 "${CLAUDE_SKILL_DIR}/size.py" --leverage 2 --write
```

Outputs:
- `crypto-trader/orders.json`
