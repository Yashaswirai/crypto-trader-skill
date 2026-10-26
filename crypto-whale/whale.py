#!/usr/bin/env python3
"""Crypto Whale & Smart Money Tracker for crypto-whale.
Tracks large block trades, exchange order-flow imbalances, and institutional accumulation.
Standard library only, zero API keys required.

    python3 whale.py scan BTCUSDT                          # scan recent block trades (default > $100k)
    python3 whale.py scan ETHUSDT --min-usd 50000          # trades > $50,000
    python3 whale.py flow BTCUSDT                          # net whale flow (Accumulation vs Distribution)
    python3 whale.py scan SOLUSDT --limit 500 --json

Outputs:
  - Whale Buy vs Sell Volume
  - Whale Net Delta (USD)
  - Institutional accumulation verdict
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
DEFAULT_MIN_WHALE_USD = 100_000.0  # $100k minimum for whale trade


def fetch_agg_trades(symbol, limit=500):
    """Fetch recent aggregate trades from public Binance endpoint."""
    headers = {"User-Agent": UA}
    endpoint = f"/api/v3/aggTrades?symbol={symbol}&limit={limit}"
    for host in BINANCE_HOSTS:
        try:
            req = urllib.request.Request(f"{host}{endpoint}", headers=headers)
            with urllib.request.urlopen(req, timeout=6) as res:
                return json.loads(res.read().decode("utf-8"))
        except Exception:
            time.sleep(0.2)
    return []


def analyze_whale_trades(trades, min_usd=DEFAULT_MIN_WHALE_USD):
    """Filter and analyze trades exceeding the whale notional threshold."""
    whale_buys = []
    whale_sells = []
    total_whale_vol_usd = 0.0

    for t in trades:
        price = float(t.get("p", 0))
        qty = float(t.get("q", 0))
        notional = price * qty
        is_buyer_maker = t.get("m", False)  # True = Sell market taker; False = Buy market taker
        trade_time = datetime.datetime.fromtimestamp(t.get("T", 0) / 1000, tz=datetime.timezone.utc).strftime("%H:%M:%S")

        if notional >= min_usd:
            trade_obj = {
                "time_utc": trade_time,
                "price": price,
                "quantity": qty,
                "usd_value": round(notional, 2),
                "side": "SELL" if is_buyer_maker else "BUY"
            }
            if is_buyer_maker:
                whale_sells.append(trade_obj)
            else:
                whale_buys.append(trade_obj)
            total_whale_vol_usd += notional

    buy_vol = sum(t["usd_value"] for t in whale_buys)
    sell_vol = sum(t["usd_value"] for t in whale_sells)
    net_flow = buy_vol - sell_vol

    if net_flow > 0.15 * total_whale_vol_usd:
        bias = "ACCUMULATION (Whales aggressively hitting the ask)"
    elif net_flow < -0.15 * total_whale_vol_usd:
        bias = "DISTRIBUTION (Whales dumping into market bids)"
    else:
        bias = "BALANCED (Two-sided large participant activity)"

    return {
        "total_trades_inspected": len(trades),
        "whale_trades_count": len(whale_buys) + len(whale_sells),
        "min_usd_threshold": min_usd,
        "whale_buy_count": len(whale_buys),
        "whale_sell_count": len(whale_sells),
        "whale_buy_volume_usd": round(buy_vol, 2),
        "whale_sell_volume_usd": round(sell_vol, 2),
        "net_whale_flow_usd": round(net_flow, 2),
        "institutional_bias": bias,
        "recent_large_trades": (whale_buys + whale_sells)[-15:]
    }


def main():
    parser = argparse.ArgumentParser(description="Crypto Whale & Smart Money Tracker (crypto-whale)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: scan
    scan_p = subparsers.add_parser("scan", help="Scan recent whale orders")
    scan_p.add_argument("symbol", help="e.g. BTCUSDT, ETHUSDT")
    scan_p.add_argument("--min-usd", type=float, default=DEFAULT_MIN_WHALE_USD)
    scan_p.add_argument("--limit", type=int, default=500)
    scan_p.add_argument("--json", action="store_true")

    # Subcommand: flow
    flow_p = subparsers.add_parser("flow", help="Calculate net whale order flow")
    flow_p.add_argument("symbol", help="e.g. BTCUSDT, ETHUSDT")
    flow_p.add_argument("--min-usd", type=float, default=DEFAULT_MIN_WHALE_USD)
    flow_p.add_argument("--json", action="store_true")

    args = parser.parse_args()

    raw_trades = fetch_agg_trades(args.symbol.upper(), limit=getattr(args, "limit", 500))
    if not raw_trades:
        print(f"Error: Unable to fetch trade tape for {args.symbol.upper()}")
        sys.exit(1)

    analysis = analyze_whale_trades(raw_trades, min_usd=args.min_usd)

    if getattr(args, "json", False):
        print(json.dumps({"symbol": args.symbol.upper(), **analysis}, indent=2))
    else:
        print(f"=== Crypto Whale Tape Analysis: {args.symbol.upper()} ===")
        print(f"Inspected Trades:  {analysis['total_trades_inspected']:,} (Threshold >= ${args.min_usd:,.0f})")
        print(f"Whale Buys:        {analysis['whale_buy_count']} orders (${analysis['whale_buy_volume_usd']:,.2f})")
        print(f"Whale Sells:       {analysis['whale_sell_count']} orders (${analysis['whale_sell_volume_usd']:,.2f})")
        print(f"Net Whale Flow:    ${analysis['net_whale_flow_usd']:>+12,.2f}")
        print(f"Institutional Bias:[{analysis['institutional_bias']}]\n")

        trades = analysis["recent_large_trades"]
        if trades:
            print("Recent Large Block Fills:")
            for t in trades[-8:]:
                side_color = "BUY " if t["side"] == "BUY" else "SELL"
                print(f"  {t['time_utc']}  [{side_color}] {t['quantity']:>8.4f} @ ${t['price']:<9.2f} (${t['usd_value']:>10,.2f})")
        else:
            print(f"No individual trades exceeded ${args.min_usd:,.0f} in the last {len(raw_trades)} tape ticks.")


if __name__ == "__main__":
    main()
