#!/usr/bin/env python3
"""Crypto News & Sentiment Monitor for crypto-news. Standard library only.

    python3 news.py fng                              # Alternative.me Crypto Fear & Greed index
    python3 news.py watchlist                        # sentiment and catalysts for symbols in crypto-trader/watchlist.json
    python3 news.py check BTCUSDT,ETHUSDT            # check specific coins
    python3 news.py fng --history 7                  # past 7 days sentiment trend

Outputs sentiment, trend shifts, and market regime context without requiring any API keys.
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
FNG_URL = "https://api.alternative.me/fng/"
BINANCE_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"
DEFAULT_WATCHLIST = "crypto-trader/watchlist.json"


def fetch_fear_and_greed(limit=7, timeout=5):
    """Fetch real-time Fear & Greed index history from Alternative.me."""
    url = f"{FNG_URL}?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("data", [])
    except Exception as e:
        return [{"value": "50", "value_classification": f"Unavailable ({e})", "timestamp": str(int(time.time()))}]


def fetch_coin_metrics(symbol, timeout=5):
    """Fetch 24h volume and price momentum for a symbol."""
    url = f"{BINANCE_URL}?symbol={symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        return {}


def evaluate_market_regime(fng_value):
    """Categorize macro market regime for risk sizing."""
    try:
        v = int(fng_value)
    except (ValueError, TypeError):
        v = 50
    if v >= 75:
        return "EXTREME_GREED", "Overheated market; watch for long-liquidation flushes and tight trailing stops."
    elif v >= 55:
        return "GREED", "Bullish momentum favored; trend-following breakout strategies optimal."
    elif v >= 45:
        return "NEUTRAL", "Balanced market; range-bound mean reversion setups preferred."
    elif v >= 25:
        return "FEAR", "Cautious sentiment; oversold bounces present favorable asymmetric R:R."
    else:
        return "EXTREME_FEAR", "Heavy capitulation; discount accumulation / high risk-premia setups."


def main():
    parser = argparse.ArgumentParser(description="Crypto Sentiment & News Monitor (crypto-news)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: fng
    fng_p = subparsers.add_parser("fng", help="Check Fear & Greed Index")
    fng_p.add_argument("--history", type=int, default=7, help="Days of history")
    fng_p.add_argument("--json", action="store_true")

    # Subcommand: watchlist
    wl_p = subparsers.add_parser("watchlist", help="Analyze sentiment & metrics for current watchlist")
    wl_p.add_argument("--file", default=DEFAULT_WATCHLIST)
    wl_p.add_argument("--json", action="store_true")

    # Subcommand: check
    chk_p = subparsers.add_parser("check", help="Check sentiment and 24h stats for symbols")
    chk_p.add_argument("symbols", help="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT")
    chk_p.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "fng":
        fng_data = fetch_fear_and_greed(limit=args.history)
        current = fng_data[0] if fng_data else {"value": "50", "value_classification": "Neutral"}
        regime, advice = evaluate_market_regime(current.get("value"))

        if args.json:
            print(json.dumps({"current": current, "regime": regime, "advice": advice, "history": fng_data}, indent=2))
        else:
            print(f"=== Crypto Fear & Greed Index ===")
            print(f"Current Value: {current.get('value')} ({current.get('value_classification')})")
            print(f"Market Regime: {regime}")
            print(f"Guidance:      {advice}\n")
            print(f"Recent Trend:")
            for item in fng_data[:args.history]:
                dt = datetime.datetime.fromtimestamp(int(item.get("timestamp", 0)), tz=datetime.timezone.utc).strftime("%Y-%m-%d")
                print(f"  {dt}: {item.get('value'):>3} - {item.get('value_classification')}")

    elif args.command == "watchlist":
        if not os.path.exists(args.file):
            print(f"No watchlist found at {args.file}. Run crypto-scanner first.")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        setups = data.get("setups", [])
        fng = fetch_fear_and_greed(limit=1)[0]
        regime, advice = evaluate_market_regime(fng.get("value"))

        print(f"=== Watchlist Sentiment Analysis ({len(setups)} pairs) ===")
        print(f"Macro Sentiment: {fng.get('value')} ({fng.get('value_classification')}) -> {regime}\n")
        for s in setups:
            sym = s.get("symbol")
            print(f"  [{s.get('setup')}] {sym:<10} ${s.get('price', 0):<10.4f} 24h: {s.get('change_24h_pct', 0):+.2f}%")
            print(f"    Catalyst: {s.get('reason')}")

    elif args.command == "check":
        syms = args.symbols.split(",")
        fng = fetch_fear_and_greed(limit=1)[0]
        results = []
        for s in syms:
            s = s.strip().upper()
            m = fetch_coin_metrics(s)
            results.append({
                "symbol": s,
                "price": float(m.get("lastPrice", 0)),
                "change_24h": float(m.get("priceChangePercent", 0)),
                "volume_usd": float(m.get("quoteVolume", 0)),
                "high_24h": float(m.get("highPrice", 0)),
                "low_24h": float(m.get("lowPrice", 0))
            })
            time.sleep(0.1)

        if args.json:
            print(json.dumps({"fng": fng, "results": results}, indent=2))
        else:
            print(f"=== Crypto Sentiment & Momentum Check ===")
            print(f"Fear & Greed: {fng.get('value')} ({fng.get('value_classification')})\n")
            for r in results:
                print(f"  {r['symbol']:<10} Price: ${r['price']:<10.4f} 24h Chg: {r['change_24h']:+.2f}% Vol: ${r['volume_usd']:>12,.0f}")


if __name__ == "__main__":
    main()
