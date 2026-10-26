#!/usr/bin/env python3
"""Crypto Position Sizer for crypto-budget: sizes trades to budget and max risk.
Standard library only, no network. Fractional token amounts with lot-size step precision.
It never places an order.

    python3 size.py                                          # reads crypto-trader/plan.json
    python3 size.py --budget 10000 --max-loss 100 --write    # risk $100 on $10k budget
    python3 size.py --leverage 2 --write                     # 2x perp leverage sizing
    python3 size.py --limit 80100 --write                    # limit order pricing

How size is calculated (smallest limit decides):
  1. max_loss:       max_loss_usd / (entry - stop)
  2. position_cap:   (budget * max_position_pct) / entry
  3. max_order:      max_order_usd / entry
  4. cash_buffer:    (budget * (1 - cash_buffer_pct)) / entry

Writes: crypto-trader/orders.json
"""

import argparse
import datetime
import json
import math
import os
import sys
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

DEFAULT_PLAN_PATH = "crypto-trader/plan.json"
DEFAULT_CONFIG_PATH = "crypto-trader/config.json"
DEFAULT_ORDERS_PATH = "crypto-trader/orders.json"

DEFAULTS = {
    "budget_usd": 5000.0,
    "max_loss_per_trade_usd": 100.0,
    "max_position_pct": 0.25,      # max 25% of budget in single coin
    "max_order_usd": 2500.0,
    "cash_buffer_pct": 0.10,       # keep 10% in USDT cash
    "default_leverage": 1,
    "min_order_usd": 10.0          # exchange minimum order size floor
}

# Standard crypto quantity step precision by price magnitude
def get_step_size(price):
    if price >= 10000:
        return Decimal("0.0001")   # BTC: 0.0001
    elif price >= 1000:
        return Decimal("0.001")    # ETH: 0.001
    elif price >= 10:
        return Decimal("0.01")     # SOL, BNB: 0.01
    elif price >= 1:
        return Decimal("0.1")      # ADA, XRP: 0.1
    else:
        return Decimal("1.0")      # DOGE, SHIB: 1


def load_config(config_path):
    cfg = dict(DEFAULTS)
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                cfg.update(user_cfg)
        except Exception:
            pass
    return cfg


def size_position(plan, config, limit_price=None, leverage=1):
    entry = Decimal(str(limit_price if limit_price else plan["entry_price"]))
    stop = Decimal(str(plan["stop_loss"]))
    target = Decimal(str(plan["take_profit"]))
    side = plan.get("side", "LONG")

    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        raise ValueError("Stop loss cannot equal entry price.")

    budget = Decimal(str(config["budget_usd"]))
    max_loss_usd = Decimal(str(config["max_loss_per_trade_usd"]))
    max_pos_pct = Decimal(str(config["max_position_pct"]))
    max_order_usd = Decimal(str(config["max_order_usd"]))
    cash_buffer_pct = Decimal(str(config["cash_buffer_pct"]))
    min_order_usd = Decimal(str(config["min_order_usd"]))

    # 1. Size by max loss
    qty_by_loss = max_loss_usd / risk_per_unit

    # 2. Size by position cap
    qty_by_pos_cap = (budget * max_pos_pct) / entry

    # 3. Size by max order
    qty_by_max_order = max_order_usd / entry

    # 4. Size by cash buffer
    usable_cash = budget * (Decimal("1") - cash_buffer_pct)
    qty_by_cash = (usable_cash * Decimal(str(leverage))) / entry

    candidates = [
        ("max_loss", qty_by_loss),
        ("position_cap", qty_by_pos_cap),
        ("max_order", qty_by_max_order),
        ("cash_buffer", qty_by_cash),
    ]

    limiting_factor, raw_qty = min(candidates, key=lambda x: x[1])

    # Round down to asset step size to respect exchange LOT_SIZE filter
    step = get_step_size(float(entry))
    steps_count = (raw_qty / step).quantize(Decimal("1"), rounding=ROUND_FLOOR)
    final_qty = steps_count * step

    notional_usd = final_qty * entry
    actual_risk_usd = final_qty * risk_per_unit

    if notional_usd < min_order_usd:
        raise ValueError(
            f"Sized order (${notional_usd:.2f}) is below minimum exchange limit (${min_order_usd:.2f})."
        )

    order = {
        "symbol": plan["symbol"],
        "side": "BUY" if side == "LONG" else "SELL",
        "type": "LIMIT" if limit_price else "MARKET",
        "quantity": float(final_qty),
        "price": float(entry),
        "stop_loss_price": float(stop),
        "take_profit_price": float(target),
        "notional_usd": float(round(notional_usd, 2)),
        "max_loss_usd": float(round(actual_risk_usd, 2)),
        "limiting_factor": limiting_factor,
        "leverage": leverage,
        "reward_to_risk": plan.get("reward_to_risk", 2.0),
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    return order


def main():
    parser = argparse.ArgumentParser(description="Crypto Position Sizer (crypto-budget)")
    parser.add_argument("--plan", default=DEFAULT_PLAN_PATH)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--out", default=DEFAULT_ORDERS_PATH)
    parser.add_argument("--budget", type=float)
    parser.add_argument("--max-loss", type=float)
    parser.add_argument("--limit", type=float)
    parser.add_argument("--leverage", type=int, default=1)
    parser.add_argument("--write", action="store_true", default=True)
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if not os.path.exists(args.plan):
        print(f"Error: Trade plan {args.plan} not found. Run crypto-exit plan first.")
        sys.exit(1)

    with open(args.plan, "r", encoding="utf-8") as f:
        plan = json.load(f)

    cfg = load_config(args.config)
    if args.budget:
        cfg["budget_usd"] = args.budget
    if args.max_loss:
        cfg["max_loss_per_trade_usd"] = args.max_loss

    try:
        order = size_position(plan, cfg, limit_price=args.limit, leverage=args.leverage)
    except Exception as e:
        print(f"Sizing Refused: {e}")
        sys.exit(1)

    if args.write:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(order, f, indent=2)

    if args.json:
        print(json.dumps(order, indent=2))
    else:
        print(f"=== Crypto Position Sizing: {order['symbol']} ({order['side']}) ===")
        print(f"Quantity:        {order['quantity']} {order['symbol'].replace('USDT', '')}")
        print(f"Entry Price:     ${order['price']:<10.4f} ({order['type']})")
        print(f"Notional Value:  ${order['notional_usd']:<10.2f}")
        print(f"Max Loss at Stop:${order['max_loss_usd']:<10.2f}")
        print(f"Limiting Rule:   {order['limiting_factor']}")
        print(f"Leverage:        {order['leverage']}x")
        if args.write:
            print(f"Bracket Order:   Saved to {args.out}")

    sys.exit(0)


if __name__ == "__main__":
    main()
