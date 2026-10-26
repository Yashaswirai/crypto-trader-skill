#!/usr/bin/env python3
"""Crypto Pre-Trade Risk Check for crypto-risk: checks proposed orders against safety limits.
Standard library only, no network. Rejects dangerous leverage, excessive losses, or revenge trading.

    python3 check.py                                   # checks crypto-trader/orders.json
    python3 check.py --orders my_order.json --json
    python3 check.py --no-write                        # test without recording verdict

What blocks an order:
  - Missing Stop Loss or Take Profit
  - Loss at stop > max_loss_per_trade_usd
  - Daily cumulative risk > max_daily_loss_usd
  - Reward:Risk < min_reward_risk (default 1.5R)
  - Leverage > max_allowed_leverage (default 5x)
  - Max trades per day reached
  - Blocked / blacklisted token
  - Duplicate order placed today

Verdict: PASS or BLOCK.
Writes: crypto-trader/state/risk.json
"""

import argparse
import datetime
import hashlib
import json
import os
import sys

DEFAULT_ORDERS_PATH = "crypto-trader/orders.json"
DEFAULT_CONFIG_PATH = "crypto-trader/config.json"
DEFAULT_STATE_RISK_PATH = "crypto-trader/state/risk.json"
DEFAULT_STATE_BROKER_PATH = "crypto-trader/state/broker.json"

DEFAULT_RULES = {
    "max_loss_per_trade_usd": 100.0,
    "max_daily_loss_usd": 300.0,
    "min_reward_risk": 1.5,
    "max_trades_per_day": 4,
    "max_leverage": 5,
    "blocked_symbols": ["LUNAUSDT", "FTTUSDT"]
}


def load_config(path):
    cfg = dict(DEFAULT_RULES)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def load_today_orders(broker_state_path):
    """Load orders already placed today to track daily cumulative risk."""
    if not os.path.exists(broker_state_path):
        return []
    try:
        with open(broker_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
            return [o for o in data if o.get("created_at_utc", "").startswith(today_str)]
    except Exception:
        return []


def fingerprint_order(order):
    """Compute deterministic SHA-256 fingerprint for order verification."""
    canonical = f"{order.get('symbol')}:{order.get('side')}:{order.get('quantity')}:{order.get('price')}:{order.get('stop_loss_price')}:{order.get('take_profit_price')}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def verify_order(order, rules, today_orders):
    sym = order.get("symbol", "").upper()
    side = order.get("side", "").upper()
    qty = float(order.get("quantity", 0))
    entry = float(order.get("price", 0))
    stop = float(order.get("stop_loss_price", 0))
    target = float(order.get("take_profit_price", 0))
    max_loss = float(order.get("max_loss_usd", 0))
    rr = float(order.get("reward_to_risk", 0))
    leverage = int(order.get("leverage", 1))

    rejections = []

    # 1. Structure check
    if not sym or not side or qty <= 0 or entry <= 0:
        rejections.append("Malformed order structure: invalid symbol, side, qty or price")
    if stop <= 0 or target <= 0:
        rejections.append("Missing stop-loss or take-profit price")

    # 2. Blocked symbol check
    if sym in rules.get("blocked_symbols", []):
        rejections.append(f"Symbol {sym} is on the blocked/blacklisted list")

    # 3. Stop direction check
    if side == "BUY" and stop >= entry:
        rejections.append(f"Stop loss ({stop}) must be below entry ({entry}) for BUY")
    if side == "SELL" and stop <= entry:
        rejections.append(f"Stop loss ({stop}) must be above entry ({entry}) for SELL")

    # 4. Max loss check
    allowed_loss = rules.get("max_loss_per_trade_usd", 100.0)
    if max_loss > allowed_loss:
        rejections.append(f"Max loss (${max_loss:.2f}) exceeds trade loss limit (${allowed_loss:.2f})")

    # 5. Reward to Risk check
    min_rr = rules.get("min_reward_risk", 1.5)
    if rr < min_rr:
        rejections.append(f"Reward:Risk ({rr:.2f}R) is below minimum required {min_rr:.1f}R")

    # 6. Leverage check
    max_lev = rules.get("max_leverage", 5)
    if leverage > max_lev:
        rejections.append(f"Leverage ({leverage}x) exceeds risk ceiling ({max_lev}x)")

    # 7. Daily trade quota & cumulative daily loss
    max_trades = rules.get("max_trades_per_day", 4)
    if len(today_orders) >= max_trades:
        rejections.append(f"Daily trade limit reached ({len(today_orders)}/{max_trades} trades placed today)")

    todays_risk = sum(float(o.get("max_loss_usd", 0)) for o in today_orders)
    daily_cap = rules.get("max_daily_loss_usd", 300.0)
    if todays_risk + max_loss > daily_cap:
        rejections.append(f"Cumulative risk (${todays_risk + max_loss:.2f}) exceeds daily loss ceiling (${daily_cap:.2f})")

    # 8. Duplicate check
    for placed in today_orders:
        if placed.get("symbol") == sym and placed.get("side") == side:
            rejections.append(f"Duplicate order: already placed a {side} order on {sym} today")
            break

    verdict = "PASS" if not rejections else "BLOCK"
    return {
        "verdict": verdict,
        "symbol": sym,
        "fingerprint": fingerprint_order(order),
        "rejections": rejections,
        "max_loss_usd": max_loss,
        "todays_cumulative_risk_usd": todays_risk,
        "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="Crypto Risk Manager (crypto-risk)")
    parser.add_argument("--orders", default=DEFAULT_ORDERS_PATH)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--state-risk", default=DEFAULT_STATE_RISK_PATH)
    parser.add_argument("--state-broker", default=DEFAULT_STATE_BROKER_PATH)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if not os.path.exists(args.orders):
        print(f"Error: Orders file {args.orders} not found. Run crypto-budget first.")
        sys.exit(1)

    with open(args.orders, "r", encoding="utf-8") as f:
        order = json.load(f)

    rules = load_config(args.config)
    today_orders = load_today_orders(args.state_broker)

    report = verify_order(order, rules, today_orders)

    if not args.no_write:
        os.makedirs(os.path.dirname(args.state_risk), exist_ok=True)
        with open(args.state_risk, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = report["verdict"]
        print(f"=== Crypto Risk Check: [{status}] ===")
        print(f"Symbol:      {report['symbol']}")
        print(f"Fingerprint: {report['fingerprint']}")
        print(f"Risk:        ${report['max_loss_usd']:.2f} (Daily Total: ${report['todays_cumulative_risk_usd'] + report['max_loss_usd']:.2f})")
        if status == "PASS":
            print(f"Status:      All risk limits satisfied. Order approved for crypto-broker.")
            if not args.no_write:
                print(f"Verdict recorded in: {args.state_risk}")
        else:
            print(f"Status:      ORDER BLOCKED BY RISK ENGINE")
            for r in report["rejections"]:
                print(f"  - {r}")

    sys.exit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
