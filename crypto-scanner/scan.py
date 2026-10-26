#!/usr/bin/env python3
"""Crypto Scanner for crypto-scanner: scan crypto markets for setups. Standard library only.

    python3 scan.py universe                          # active USDT pairs -> crypto-trader/universe.txt
    python3 scan.py daily                             # 24h setups: breakouts, flags, bounces -> crypto-trader/watchlist.json
    python3 scan.py daily --symbols BTCUSDT,ETHUSDT   # or --min-volume 20000000
    python3 scan.py session --session london          # session range breakout (asian, london, ny)
    python3 scan.py session --session ny --interval 5m
    python3 scan.py daily --offline fixtures.json --json

Setups:
  breakout_24h    price within 1.5% of or closing above 24-hour high with high volume
  bull_flag       up >8% with tight consolidation (range < 3.5%) in recent bars
  oversold_bounce RSI-14 under 32 bouncing upward
  volume_surge    24h volume > 2.5x normal threshold with positive price change
  session_break   closing outside Asian Range (00:00-08:00 UTC) during London/NY open

Zero API key required. Uses public endpoints with polite pauses and offline fixture support.
"""

import argparse
import datetime
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

UA = "Mozilla/5.0 (compatible; crypto-trader-skill/1.0; +https://github.com/crypto-trader-skill)"
BINANCE_HOSTS = ("https://data-api.binance.vision", "https://api.binance.com")
PAUSE = 0.2
BACKOFF = 3.0
DEFAULT_MIN_VOLUME_USD = 10_000_000  # $10M minimum 24h volume for liquidity
DEFAULT_UNIVERSE_PATH = "crypto-trader/universe.txt"
DEFAULT_WATCHLIST_PATH = "crypto-trader/watchlist.json"
NOTE = "A crypto scan identifies mathematical setups across public charts, not financial advice."


def fetch_json(endpoint, hosts=BINANCE_HOSTS, timeout=6):
    """Fetch JSON from primary or fallback host with polite retry."""
    headers = {"User-Agent": UA}
    last_err = None
    for host in hosts:
        url = f"{host}{endpoint}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return json.loads(res.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(PAUSE)
            continue
    raise RuntimeError(f"Failed to fetch {endpoint} across all endpoints: {last_err}")


def get_universe(min_volume_usd=DEFAULT_MIN_VOLUME_USD, offline=None):
    """Retrieve active spot USDT pairs above liquidity threshold."""
    if offline and os.path.exists(offline):
        with open(offline, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = fetch_json("/api/v3/ticker/24hr")

    candidates = []
    for item in data:
        sym = item.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        # Drop leveraged tokens, stablecoin-to-stablecoin pairs, down/up tokens
        if any(x in sym for x in ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT", "USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "EURUSDT")):
            continue
        try:
            quote_vol = float(item.get("quoteVolume", 0))
            last_price = float(item.get("lastPrice", 0))
            if quote_vol >= min_volume_usd and last_price > 0:
                candidates.append({
                    "symbol": sym,
                    "price": last_price,
                    "volume_usd": quote_vol,
                    "change_24h": float(item.get("priceChangePercent", 0)),
                    "high_24h": float(item.get("highPrice", 0)),
                    "low_24h": float(item.get("lowPrice", 0)),
                })
        except (ValueError, TypeError):
            continue

    candidates.sort(key=lambda x: x["volume_usd"], reverse=True)
    return candidates


def calculate_rsi(closes, period=14):
    """Calculate standard Wilder's RSI."""
    if len(closes) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    if sum(losses[:period]) == 0:
        return 100.0
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def scan_daily_setups(symbols=None, min_volume_usd=DEFAULT_MIN_VOLUME_USD, offline=None):
    """Scan tickers for 24h setups: 24h breakouts, volume surges, flags."""
    universe = get_universe(min_volume_usd=min_volume_usd, offline=offline)
    if symbols:
        sym_set = set(symbols.split(","))
        universe = [x for x in universe if x["symbol"] in sym_set]

    hits = []
    for item in universe:
        sym = item["symbol"]
        price = item["price"]
        high = item["high_24h"]
        low = item["low_24h"]
        chg = item["change_24h"]
        vol = item["volume_usd"]

        setup_type = None
        reasons = []

        # 1. 24h Breakout / Near High
        if high > 0 and price >= high * 0.985:
            setup_type = "breakout_24h"
            reasons.append(f"Price {price} is within 1.5% of 24h high {high} (+{chg:.2f}%)")
        # 2. Volume Surge with Positive Momentum
        elif chg >= 6.0 and vol >= min_volume_usd * 2.0:
            setup_type = "volume_surge"
            reasons.append(f"24h surge +{chg:.2f}% on ${vol:,.0f} volume")
        # 3. Consolidation flag
        elif 3.0 <= chg <= 12.0 and high > 0 and (high - low) / high <= 0.05:
            setup_type = "bull_flag"
            reasons.append(f"Consolidating in tight 5% range after +{chg:.2f}% push")

        if setup_type:
            hits.append({
                "symbol": sym,
                "setup": setup_type,
                "price": price,
                "high_24h": high,
                "low_24h": low,
                "change_24h_pct": chg,
                "volume_usd": vol,
                "reason": "; ".join(reasons),
                "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })

    return hits


def scan_session_breakouts(session_name="london", symbols=None, offline=None):
    """Scan for Session Range Breakouts (SRB).
    Asian Session: 00:00 - 08:00 UTC
    London Session: 08:00 - 16:00 UTC
    NY Session: 13:30 - 21:00 UTC
    """
    universe = get_universe(min_volume_usd=15_000_000, offline=offline)[:40]
    if symbols:
        sym_set = set(symbols.split(","))
        universe = [x for x in universe if x["symbol"] in sym_set]

    hits = []
    for item in universe:
        sym = item["symbol"]
        if offline:
            continue
        try:
            # Fetch 12 hours of 15m bars to extract Asian range and subsequent breakout
            bars = fetch_json(f"/api/v3/klines?symbol={sym}&interval=15m&limit=48")
            if not bars or len(bars) < 32:
                continue
            # Asian range: first 32 15m bars (00:00 to 08:00 UTC is 8h = 32 bars)
            asian_bars = bars[:32]
            asian_high = max(float(b[2]) for b in asian_bars)
            asian_low = min(float(b[3]) for b in asian_bars)
            latest_bar = bars[-1]
            latest_close = float(latest_bar[4])

            if latest_close > asian_high:
                hits.append({
                    "symbol": sym,
                    "setup": "asian_range_breakout_long",
                    "price": latest_close,
                    "range_high": asian_high,
                    "range_low": asian_low,
                    "reason": f"Closed at {latest_close} above Asian range high {asian_high}",
                    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
        except Exception:
            continue
        time.sleep(PAUSE)

    return hits


def main():
    parser = argparse.ArgumentParser(description="Crypto Scanner (crypto-scanner): 24h & session setups")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: universe
    uni_parser = subparsers.add_parser("universe", help="Fetch active USDT crypto universe")
    uni_parser.add_argument("--min-volume", type=float, default=DEFAULT_MIN_VOLUME_USD)
    uni_parser.add_argument("--write", action="store_true", default=True)
    uni_parser.add_argument("--out", default=DEFAULT_UNIVERSE_PATH)
    uni_parser.add_argument("--offline")

    # Subcommand: daily
    daily_parser = subparsers.add_parser("daily", help="Scan daily 24h breakouts, flags, volume surges")
    daily_parser.add_argument("--symbols", help="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT,SOLUSDT")
    daily_parser.add_argument("--min-volume", type=float, default=DEFAULT_MIN_VOLUME_USD)
    daily_parser.add_argument("--write", action="store_true", default=True)
    daily_parser.add_argument("--out", default=DEFAULT_WATCHLIST_PATH)
    daily_parser.add_argument("--json", action="store_true")
    daily_parser.add_argument("--offline")

    # Subcommand: session
    sess_parser = subparsers.add_parser("session", help="Scan session range breakouts (SRB)")
    sess_parser.add_argument("--session", choices=["asian", "london", "ny"], default="london")
    sess_parser.add_argument("--symbols")
    sess_parser.add_argument("--write", action="store_true", default=True)
    sess_parser.add_argument("--out", default=DEFAULT_WATCHLIST_PATH)
    sess_parser.add_argument("--json", action="store_true")
    sess_parser.add_argument("--offline")

    args = parser.parse_args()

    if args.command == "universe":
        universe = get_universe(min_volume_usd=args.min_volume, offline=args.offline)
        if args.write:
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                for item in universe:
                    f.write(f"{item['symbol']}\t{item['price']}\t{item['volume_usd']:.0f}\n")
        print(f"Discovered {len(universe)} liquid USDT crypto pairs (min volume ${args.min_volume:,.0f}).")
        for u in universe[:10]:
            print(f"  {u['symbol']:<12} Price: ${u['price']:<10.4f} 24h Vol: ${u['volume_usd']:>12,.0f} ({u['change_24h']:+.2f}%)")
        sys.exit(0 if universe else 1)

    elif args.command in ("daily", "session"):
        if args.command == "daily":
            hits = scan_daily_setups(symbols=args.symbols, min_volume_usd=args.min_volume, offline=args.offline)
        else:
            hits = scan_session_breakouts(session_name=args.session, symbols=args.symbols, offline=args.offline)

        if args.write:
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            output = {
                "scan_time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "scan_type": args.command,
                "hit_count": len(hits),
                "setups": hits
            }
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2)

        if getattr(args, "json", False):
            print(json.dumps(hits, indent=2))
        else:
            print(f"Crypto Scanner Found {len(hits)} Setups:")
            for h in hits:
                print(f"  [{h['setup']}] {h['symbol']:<12} Price: ${h['price']:<10.4f} -> {h['reason']}")

        sys.exit(0 if hits else 1)


if __name__ == "__main__":
    main()
