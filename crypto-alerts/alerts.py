#!/usr/bin/env python3
"""Crypto Price & Session Alerts for crypto-alerts.
Monitors price thresholds, stops, targets, session opens, and funding settlement windows.
Standard library only.

    python3 alerts.py check BTCUSDT                                # get latest price & cache
    python3 alerts.py plan                                         # watch stops and targets in crypto-trader/plan.json
    python3 alerts.py alert BTCUSDT --above 81000                  # price breakout alert
    python3 alerts.py alert SOLUSDT --below 175.00                 # breakdown alert
    python3 alerts.py funding                                      # next 8h funding settlement reminder
    python3 alerts.py sessions                                     # countdown to Asian, London, NY opens

Writes: crypto-trader/prices.json
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; crypto-trader-skill/1.0; +https://github.com/crypto-trader-skill)"
BINANCE_HOSTS = ("https://data-api.binance.vision", "https://api.binance.com")
DEFAULT_PLAN_PATH = "crypto-trader/plan.json"
DEFAULT_PRICES_PATH = "crypto-trader/prices.json"


def fetch_ticker(symbol):
    """Fetch real-time ticker quote from Binance public endpoint."""
    headers = {"User-Agent": UA}
    endpoint = f"/api/v3/ticker/24hr?symbol={symbol}"
    for host in BINANCE_HOSTS:
        try:
            req = urllib.request.Request(f"{host}{endpoint}", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as res:
                d = json.loads(res.read().decode("utf-8"))
                return {
                    "symbol": symbol,
                    "price": float(d.get("lastPrice", 0)),
                    "change_24h_pct": float(d.get("priceChangePercent", 0)),
                    "high_24h": float(d.get("highPrice", 0)),
                    "low_24h": float(d.get("lowPrice", 0)),
                    "volume_usd": float(d.get("quoteVolume", 0)),
                    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
        except Exception:
            time.sleep(0.1)
    return None


def update_prices_cache(quote, cache_path=DEFAULT_PRICES_PATH):
    """Save quote into crypto-trader/prices.json."""
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    prices = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                prices = json.load(f)
        except Exception:
            pass
    prices[quote["symbol"]] = quote
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(prices, f, indent=2)


def check_plan_alerts(plan, quote):
    """Check if stop, target, or time-stop is triggered."""
    price = quote["price"]
    entry = plan["entry_price"]
    stop = plan["stop_loss"]
    target = plan["take_profit"]
    side = plan.get("side", "LONG")

    alerts = []
    if side == "LONG":
        if price <= stop:
            alerts.append(f"STOP LOSS HIT! Price ${price:.4f} <= Stop ${stop:.4f}")
        elif price >= target:
            alerts.append(f"TAKE PROFIT HIT! Price ${price:.4f} >= Target ${target:.4f}")
        else:
            dist_stop = ((price - stop) / price) * 100.0
            dist_target = ((target - price) / price) * 100.0
            alerts.append(f"In trade: Price ${price:.4f} | {dist_stop:.2f}% to Stop | {dist_target:.2f}% to Target")

    flat_by_str = plan.get("flat_by_utc")
    if flat_by_str:
        flat_by = datetime.datetime.fromisoformat(flat_by_str)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if now_utc >= flat_by:
            alerts.append(f"TIME STOP EXPIRED! Exceeded max hold window ({plan.get('max_hold_hours')} hours). Close position.")
        else:
            mins_left = int((flat_by - now_utc).total_seconds() / 60)
            alerts.append(f"Holding time: {mins_left} minutes remaining until flat-by window")

    return alerts


def get_funding_settlement_info():
    """Calculate time remaining until next 8-hour funding settlement (00:00, 08:00, 16:00 UTC)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    current_hour = now.hour
    next_hour = ((current_hour // 8) + 1) * 8
    if next_hour >= 24:
        next_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    else:
        next_dt = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)

    diff = next_dt - now
    total_seconds = int(diff.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return next_dt.strftime("%H:%M UTC"), hours, minutes


def get_session_clocks():
    """Report countdown to major global session windows."""
    now = datetime.datetime.now(datetime.timezone.utc)
    sessions = [
        ("Asian Session", 0, 0),
        ("London Session", 8, 0),
        ("New York Session", 13, 30),
    ]
    report = []
    for name, h, m in sessions:
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        diff = target - now
        total_seconds = int(diff.total_seconds())
        hrs, rem = divmod(total_seconds, 3600)
        mins = rem // 60
        report.append({"name": name, "time_utc": f"{h:02d}:{m:02d} UTC", "in_hours": hrs, "in_mins": mins})
    return report


def main():
    parser = argparse.ArgumentParser(description="Crypto Alerts Monitor (crypto-alerts)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check
    chk_p = subparsers.add_parser("check", help="Fetch price & update cache")
    chk_p.add_argument("symbol")

    # Subcommand: plan
    plan_p = subparsers.add_parser("plan", help="Check active trade plan alerts")
    plan_p.add_argument("--plan", default=DEFAULT_PLAN_PATH)

    # Subcommand: alert
    al_p = subparsers.add_parser("alert", help="Check custom price threshold")
    al_p.add_argument("symbol")
    al_p.add_argument("--above", type=float)
    al_p.add_argument("--below", type=float)

    # Subcommand: funding
    subparsers.add_parser("funding", help="Show countdown to next 8h funding rate settlement")

    # Subcommand: sessions
    subparsers.add_parser("sessions", help="Show global session windows")

    args = parser.parse_args()

    if args.command == "check":
        quote = fetch_ticker(args.symbol.upper())
        if not quote:
            print(f"Error: Unable to fetch quote for {args.symbol}")
            sys.exit(1)
        update_prices_cache(quote)
        print(f"{quote['symbol']}: ${quote['price']:.4f} ({quote['change_24h_pct']:+.2f}%) | 24h Vol: ${quote['volume_usd']:,.0f}")

    elif args.command == "plan":
        if not os.path.exists(args.plan):
            print(f"No active trade plan at {args.plan}.")
            sys.exit(1)
        with open(args.plan, "r", encoding="utf-8") as f:
            plan = json.load(f)
        quote = fetch_ticker(plan["symbol"])
        if not quote:
            print(f"Error fetching quote for {plan['symbol']}")
            sys.exit(1)
        update_prices_cache(quote)
        alerts = check_plan_alerts(plan, quote)
        print(f"=== Plan Alert Check: {plan['symbol']} ===")
        for a in alerts:
            print(f"  * {a}")

    elif args.command == "alert":
        quote = fetch_ticker(args.symbol.upper())
        if not quote:
            print(f"Error fetching quote for {args.symbol}")
            sys.exit(1)
        price = quote["price"]
        triggered = False
        if args.above and price >= args.above:
            print(f"ALERT TRIGGERED! {args.symbol} price ${price:.4f} is ABOVE threshold ${args.above:.4f}")
            triggered = True
        elif args.below and price <= args.below:
            print(f"ALERT TRIGGERED! {args.symbol} price ${price:.4f} is BELOW threshold ${args.below:.4f}")
            triggered = True
        else:
            print(f"No trigger: {args.symbol} is currently ${price:.4f}")
        sys.exit(0 if triggered else 1)

    elif args.command == "funding":
        f_time, h, m = get_funding_settlement_info()
        print(f"Next Funding Settlement: {f_time} (in {h} hours, {m} minutes)")
        print("Note: In perpetual futures, funding fees are deducted or credited at this boundary.")

    elif args.command == "sessions":
        sessions = get_session_clocks()
        print("=== Global Crypto Trading Sessions (UTC) ===")
        for s in sessions:
            print(f"  {s['name']:<18} {s['time_utc']} -> in {s['in_hours']}h {s['in_mins']}m")


if __name__ == "__main__":
    main()
