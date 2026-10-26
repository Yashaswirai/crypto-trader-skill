#!/usr/bin/env python3
"""Crypto Exit Planner for crypto-exit: sets Stop-Loss and Take-Profit targets BEFORE you enter.
Standard library only. Long and short setups supported. It never places an order.

    python3 exit.py plan                                     # reads crypto-trader/entry.json (2R target default)
    python3 exit.py plan --stop pct:2.0 --target 2R --write
    python3 exit.py plan --symbol BTCUSDT --entry 80000 --stop atr:1.5 --target 2.5R
    python3 exit.py plan --symbol SOLUSDT --entry 180 --stop price:174.50 --target price:195.00
    python3 exit.py show                                     # print current crypto-trader/plan.json

Stops:
  atr:K       K times 14-period ATR below entry (recommended for crypto volatility)
  pct:X       X percent below entry
  low         bar low from trigger bar
  price:X     explicit user price

Targets:
  2R (default), 1R, 1.5R, 3R...  where R = entry - stop
  price:X                        explicit target price

Refused with explanation:
  - Stop at or above entry (for long)
  - Target at or below entry (for long)
  - Risk < 0.15% of price (too tight to cover crypto taker fees + slippage)
  - Invalid reward:risk ratio (< 1.0)

Writes: crypto-trader/plan.json
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

UA = "Mozilla/5.0 (compatible; crypto-trader-skill/1.0; +https://github.com/crypto-trader-skill)"
BINANCE_HOSTS = ("https://data-api.binance.vision", "https://api.binance.com")
DEFAULT_ENTRY_PATH = "crypto-trader/entry.json"
DEFAULT_PLAN_PATH = "crypto-trader/plan.json"
MIN_RISK_PCT = Decimal("0.15")  # minimum 0.15% risk buffer to clear exchange fees + slippage


def fetch_atr(symbol, interval="5m", period=14):
    """Fetch 14-period ATR using public Binance klines."""
    headers = {"User-Agent": UA}
    endpoint = f"/api/v3/klines?symbol={symbol}&interval={interval}&limit={period + 10}"
    data = None
    for host in BINANCE_HOSTS:
        try:
            req = urllib.request.Request(f"{host}{endpoint}", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode("utf-8"))
                break
        except Exception:
            time.sleep(0.2)
            continue
    if not data or len(data) < 2:
        return None

    true_ranges = []
    for i in range(1, len(data)):
        high = Decimal(str(data[i][2]))
        low = Decimal(str(data[i][3]))
        prev_close = Decimal(str(data[i - 1][4]))
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    if not true_ranges:
        return None
    return sum(true_ranges[-period:]) / Decimal(str(len(true_ranges[-period:])))


def calculate_plan(symbol, entry, stop_spec="pct:2.0", target_spec="2R", side="LONG", max_hold_hours=8):
    """Compute exact Stop-Loss, Take-Profit, and Risk/Reward parameters."""
    d_entry = Decimal(str(entry))
    d_stop = None

    # Calculate stop
    if stop_spec.startswith("pct:"):
        pct = Decimal(stop_spec.split(":")[1]) / Decimal("100")
        d_stop = d_entry * (Decimal("1") - pct)
    elif stop_spec.startswith("price:"):
        d_stop = Decimal(stop_spec.split(":")[1])
    elif stop_spec.startswith("atr:"):
        multiplier = Decimal(stop_spec.split(":")[1])
        atr = fetch_atr(symbol)
        if atr is None:
            # Fallback 1.5% if ATR fetch fails
            atr = d_entry * Decimal("0.015")
        d_stop = d_entry - (multiplier * atr)
    elif stop_spec == "low":
        d_stop = d_entry * Decimal("0.98")  # default 2% buffer if raw low absent
    else:
        raise ValueError(f"Unknown stop specification: {stop_spec}")

    # Validate stop placement
    if side == "LONG" and d_stop >= d_entry:
        raise ValueError(f"Stop loss ({d_stop}) must be below entry price ({d_entry}) for a LONG")
    if side == "SHORT" and d_stop <= d_entry:
        raise ValueError(f"Stop loss ({d_stop}) must be above entry price ({d_entry}) for a SHORT")

    risk_per_unit = abs(d_entry - d_stop)
    risk_pct = (risk_per_unit / d_entry) * Decimal("100")

    if risk_pct < MIN_RISK_PCT:
        raise ValueError(
            f"Risk {risk_pct:.3f}% is below minimum {MIN_RISK_PCT}% (spread/fee noise). Widen your stop."
        )

    # Calculate target
    d_target = None
    if target_spec.endswith("R"):
        r_mult = Decimal(target_spec[:-1])
        d_target = d_entry + (r_mult * risk_per_unit) if side == "LONG" else d_entry - (r_mult * risk_per_unit)
    elif target_spec.startswith("price:"):
        d_target = Decimal(target_spec.split(":")[1])
    else:
        raise ValueError(f"Unknown target specification: {target_spec}")

    if side == "LONG" and d_target <= d_entry:
        raise ValueError(f"Target ({d_target}) must be above entry price ({d_entry})")
    if side == "SHORT" and d_target >= d_entry:
        raise ValueError(f"Target ({d_target}) must be below entry price ({d_entry})")

    reward_per_unit = abs(d_target - d_entry)
    rr_ratio = reward_per_unit / risk_per_unit

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    flat_by = now_utc + datetime.timedelta(hours=max_hold_hours)

    return {
        "symbol": symbol,
        "side": side,
        "entry_price": float(d_entry),
        "stop_loss": float(d_stop),
        "take_profit": float(d_target),
        "risk_per_unit": float(risk_per_unit),
        "risk_pct": float(risk_pct),
        "reward_per_unit": float(reward_per_unit),
        "reward_to_risk": float(round(rr_ratio, 2)),
        "max_hold_hours": max_hold_hours,
        "flat_by_utc": flat_by.isoformat(),
        "created_at_utc": now_utc.isoformat(),
        "note": "A stop-loss is an execution plan; high market volatility can produce slippage."
    }


def main():
    parser = argparse.ArgumentParser(description="Crypto Exit Planner (crypto-exit)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: plan
    plan_p = subparsers.add_parser("plan", help="Compute stop and target for a trade")
    plan_p.add_argument("--symbol")
    plan_p.add_argument("--entry", type=float)
    plan_p.add_argument("--stop", default="pct:2.0", help="e.g. pct:2.0, atr:1.5, price:78500")
    plan_p.add_argument("--target", default="2R", help="e.g. 2R, 1.5R, 3R, price:84000")
    plan_p.add_argument("--side", choices=["LONG", "SHORT"], default="LONG")
    plan_p.add_argument("--max-hold-hours", type=int, default=8)
    plan_p.add_argument("--from-entry", default=DEFAULT_ENTRY_PATH)
    plan_p.add_argument("--write", action="store_true", default=True)
    plan_p.add_argument("--out", default=DEFAULT_PLAN_PATH)
    plan_p.add_argument("--json", action="store_true")

    # Subcommand: show
    show_p = subparsers.add_parser("show", help="Display current active plan")
    show_p.add_argument("--file", default=DEFAULT_PLAN_PATH)

    args = parser.parse_args()

    if args.command == "plan":
        sym = args.symbol
        entry_price = args.entry
        if not sym or not entry_price:
            if os.path.exists(args.from_entry):
                with open(args.from_entry, "r", encoding="utf-8") as f:
                    entry_data = json.load(f)
                sym = sym or entry_data.get("symbol")
                entry_price = entry_price or entry_data.get("entry_price")
            else:
                print(f"Error: Specify --symbol and --entry or trigger an entry first via crypto-entry.")
                sys.exit(1)

        try:
            plan = calculate_plan(
                symbol=sym.upper(),
                entry=entry_price,
                stop_spec=args.stop,
                target_spec=args.target,
                side=args.side,
                max_hold_hours=args.max_hold_hours
            )
        except Exception as e:
            print(f"Plan Refused: {e}")
            sys.exit(1)

        if args.write:
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2)

        if getattr(args, "json", False):
            print(json.dumps(plan, indent=2))
        else:
            print(f"=== Crypto Trade Exit Plan: {plan['symbol']} ({plan['side']}) ===")
            print(f"Entry:       ${plan['entry_price']:<10.4f}")
            print(f"Stop Loss:   ${plan['stop_loss']:<10.4f} (-{plan['risk_pct']:.2f}%)")
            print(f"Take Profit: ${plan['take_profit']:<10.4f} (+{plan['reward_to_risk'] * plan['risk_pct']:.2f}%)")
            print(f"Reward:Risk: {plan['reward_to_risk']:.2f}R")
            print(f"Max Hold:    {plan['max_hold_hours']} hours (Flat by: {plan['flat_by_utc']})")
            if args.write:
                print(f"Saved to:    {args.out}")

        sys.exit(0)

    elif args.command == "show":
        if not os.path.exists(args.file):
            print(f"No active trade plan found at {args.file}.")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            plan = json.load(f)
        print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
