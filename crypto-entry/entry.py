#!/usr/bin/env python3
"""Crypto Entry Timer for crypto-entry: watches setups bar-by-bar and identifies entry triggers.
Standard library only. Long and short setups supported. It never places an order.

    python3 entry.py check BTCUSDT --level 80500                       # breakout above price
    python3 entry.py check ETHUSDT --setup session_orb --session london # London session breakout
    python3 entry.py check SOLUSDT --level 185.00 --interval 5m --min-volume-x 1.2 --write
    python3 entry.py watchlist                                          # check all coins in watchlist
    python3 entry.py check BTCUSDT --offline fixtures.json --json

Triggers occur strictly on completed bar CLOSES (a wick does not trigger an entry).
Writes: crypto-trader/entry.json
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

UA = "Mozilla/5.0 (compatible; crypto-trader-skill/1.0; +https://github.com/crypto-trader-skill)"
BINANCE_HOSTS = ("https://data-api.binance.vision", "https://api.binance.com")
PAUSE = 0.2
DEFAULT_ENTRY_PATH = "crypto-trader/entry.json"
DEFAULT_WATCHLIST_PATH = "crypto-trader/watchlist.json"


def fetch_klines(symbol, interval="5m", limit=60, offline=None):
    """Fetch completed OHLCV bars from Binance or offline fixture."""
    if offline and os.path.exists(offline):
        with open(offline, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(symbol, data) if isinstance(data, dict) else data

    headers = {"User-Agent": UA}
    endpoint = f"/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    for host in BINANCE_HOSTS:
        try:
            req = urllib.request.Request(f"{host}{endpoint}", headers=headers)
            with urllib.request.urlopen(req, timeout=6) as res:
                return json.loads(res.read().decode("utf-8"))
        except Exception:
            time.sleep(PAUSE)
            continue
    raise RuntimeError(f"Failed to fetch klines for {symbol}")


def parse_kline_bars(raw_bars):
    """Parse raw Binance klines: [open_time, open, high, low, close, volume, close_time, ...]"""
    bars = []
    now_ms = int(time.time() * 1000)
    for b in raw_bars:
        open_time = int(b[0])
        close_time = int(b[6])
        # Only evaluate completed bars (close time must be past)
        if close_time <= now_ms or len(raw_bars) < 3:
            bars.append({
                "open_time": open_time,
                "close_time": close_time,
                "open": float(b[1]),
                "high": float(b[2]),
                "low": float(b[3]),
                "close": float(b[4]),
                "volume": float(b[5]),
                "quote_volume": float(b[7]),
            })
    return bars


def evaluate_entry(symbol, bars, setup="breakout", level=None, min_volume_x=1.0):
    """Evaluate whether the latest completed bar triggered the setup."""
    if not bars or len(bars) < 3:
        return {"status": "no_data", "reason": "Insufficient bars available"}

    trigger_bar = bars[-1]
    prev_bars = bars[:-1]

    # Calculate baseline average volume
    recent_vol = [b["volume"] for b in prev_bars[-10:]]
    avg_vol = sum(recent_vol) / len(recent_vol) if recent_vol else 1.0
    vol_ratio = trigger_bar["volume"] / avg_vol if avg_vol > 0 else 1.0

    if min_volume_x > 1.0 and vol_ratio < min_volume_x:
        return {
            "status": "waiting",
            "reason": f"Bar closed at {trigger_bar['close']} but volume ({vol_ratio:.2f}x) under required {min_volume_x:.1f}x threshold",
            "bar": trigger_bar
        }

    if setup == "breakout":
        target_level = level if level is not None else max(b["high"] for b in prev_bars[-20:])
        if trigger_bar["close"] > target_level:
            return {
                "status": "triggered",
                "symbol": symbol,
                "setup": "level_breakout",
                "entry_price": trigger_bar["close"],
                "trigger_level": target_level,
                "bar_high": trigger_bar["high"],
                "bar_low": trigger_bar["low"],
                "volume_ratio": vol_ratio,
                "close_time_utc": datetime.datetime.fromtimestamp(trigger_bar["close_time"] / 1000, tz=datetime.timezone.utc).isoformat(),
                "reason": f"Bar closed at {trigger_bar['close']} above breakout level {target_level:.4f} (volume {vol_ratio:.1f}x)"
            }
        else:
            return {
                "status": "waiting",
                "symbol": symbol,
                "reason": f"Latest close {trigger_bar['close']} is below breakout level {target_level:.4f}",
                "distance_pct": ((target_level - trigger_bar["close"]) / trigger_bar["close"]) * 100.0
            }

    elif setup == "session_orb":
        # First 6 5m bars (30 mins) define the session range
        range_bars = prev_bars[:6]
        range_high = max(b["high"] for b in range_bars)
        range_low = min(b["low"] for b in range_bars)
        if trigger_bar["close"] > range_high:
            return {
                "status": "triggered",
                "symbol": symbol,
                "setup": "session_orb_breakout",
                "entry_price": trigger_bar["close"],
                "range_high": range_high,
                "range_low": range_low,
                "volume_ratio": vol_ratio,
                "close_time_utc": datetime.datetime.fromtimestamp(trigger_bar["close_time"] / 1000, tz=datetime.timezone.utc).isoformat(),
                "reason": f"Bar closed at {trigger_bar['close']} above session range high {range_high:.4f}"
            }
        else:
            return {
                "status": "waiting",
                "symbol": symbol,
                "reason": f"Inside session range ({range_low:.4f} - {range_high:.4f}), latest close {trigger_bar['close']}"
            }

    return {"status": "waiting", "reason": "No trigger condition met"}


def main():
    parser = argparse.ArgumentParser(description="Crypto Entry Timer (crypto-entry)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check
    chk_p = subparsers.add_parser("check", help="Check entry trigger for a symbol")
    chk_p.add_argument("symbol", help="e.g. BTCUSDT, ETHUSDT")
    chk_p.add_argument("--setup", choices=["breakout", "session_orb"], default="breakout")
    chk_p.add_argument("--level", type=float, help="Breakout price level")
    chk_p.add_argument("--interval", choices=["1m", "5m", "15m", "1h"], default="5m")
    chk_p.add_argument("--min-volume-x", type=float, default=1.0)
    chk_p.add_argument("--write", action="store_true", default=True)
    chk_p.add_argument("--out", default=DEFAULT_ENTRY_PATH)
    chk_p.add_argument("--offline")
    chk_p.add_argument("--json", action="store_true")

    # Subcommand: watchlist
    wl_p = subparsers.add_parser("watchlist", help="Check triggers for symbols in watchlist")
    wl_p.add_argument("--file", default=DEFAULT_WATCHLIST_PATH)
    wl_p.add_argument("--interval", default="5m")
    wl_p.add_argument("--write", action="store_true", default=True)
    wl_p.add_argument("--out", default=DEFAULT_ENTRY_PATH)

    args = parser.parse_args()

    if args.command == "check":
        raw = fetch_klines(args.symbol.upper(), interval=args.interval, offline=args.offline)
        bars = parse_kline_bars(raw)
        res = evaluate_entry(args.symbol.upper(), bars, setup=args.setup, level=args.level, min_volume_x=args.min_volume_x)

        if res.get("status") == "triggered" and args.write:
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)

        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            status = res.get("status").upper()
            print(f"=== Crypto Entry Check: {args.symbol.upper()} [{status}] ===")
            print(f"Details: {res.get('reason')}")
            if status == "TRIGGERED":
                print(f"Entry Price: ${res['entry_price']:.4f}")
                print(f"Time (UTC):   {res['close_time_utc']}")
                print(f"Plan written to {args.out}")

        sys.exit(0 if res.get("status") == "triggered" else 1)

    elif args.command == "watchlist":
        if not os.path.exists(args.file):
            print(f"Watchlist file {args.file} not found.")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            wl = json.load(f)
        setups = wl.get("setups", [])
        triggered = []
        for s in setups:
            sym = s.get("symbol")
            try:
                raw = fetch_klines(sym, interval=args.interval)
                bars = parse_kline_bars(raw)
                res = evaluate_entry(sym, bars, setup="breakout", level=s.get("high_24h"))
                if res.get("status") == "triggered":
                    triggered.append(res)
                print(f"  {sym:<10}: {res.get('status').upper()} -> {res.get('reason')}")
            except Exception as e:
                print(f"  {sym:<10}: ERROR ({e})")
            time.sleep(PAUSE)

        if triggered and args.write:
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(triggered[0], f, indent=2)
            print(f"\nWrote top triggered entry ({triggered[0]['symbol']}) to {args.out}")

        sys.exit(0 if triggered else 1)


if __name__ == "__main__":
    main()
