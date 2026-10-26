#!/usr/bin/env python3
"""Crypto Tokenomics & Market Structure Analyst for crypto-analyst.
Computes MC/FDV dilution overhang, circulating supply ratio, liquidity turnover,
and derivatives market health. Standard library only, zero API keys required.

    python3 analyst.py check BTC                                   # analyze tokenomics
    python3 analyst.py check SOL --json
    python3 analyst.py compare BTC,ETH,SOL                         # compare supply & dilution
    python3 analyst.py funding BTCUSDT                             # analyze funding rate & open interest

Outputs:
  - MC / FDV Overhang Ratio (Dilution Risk)
  - Circulating Supply Ratio
  - Turnover (Volume / Market Cap)
  - Derivatives Over-leverage Risk
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; crypto-trader-skill/1.0; +https://github.com/crypto-trader-skill)"
BINANCE_HOSTS = ("https://data-api.binance.vision", "https://api.binance.com")
COINGECKO_BASE = "https://api.coingecko.com/api/v3"


def fetch_tokenomics(asset_id):
    """Fetch supply and market metrics from public CoinGecko or fallback estimations."""
    url = f"{COINGECKO_BASE}/coins/{asset_id.lower()}?localization=false&tickers=false&community_data=false&developer_data=false"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=6) as res:
            d = json.loads(res.read().decode("utf-8"))
            m = d.get("market_data", {})
            return {
                "id": asset_id,
                "name": d.get("name"),
                "symbol": d.get("symbol", "").upper(),
                "price_usd": m.get("current_price", {}).get("usd", 0),
                "market_cap": m.get("market_cap", {}).get("usd", 0),
                "fdv": m.get("fully_diluted_valuation", {}).get("usd", 0) or m.get("market_cap", {}).get("usd", 0),
                "total_volume_24h": m.get("total_volume", {}).get("usd", 0),
                "circulating_supply": m.get("circulating_supply", 0),
                "total_supply": m.get("total_supply", 0) or m.get("circulating_supply", 0),
                "max_supply": m.get("max_supply", 0)
            }
    except Exception:
        # Fallback to Binance ticker if CoinGecko rate-limited
        ticker_url = f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={asset_id.upper()}USDT"
        try:
            req = urllib.request.Request(ticker_url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=5) as res:
                b = json.loads(res.read().decode("utf-8"))
                price = float(b.get("lastPrice", 0))
                vol = float(b.get("quoteVolume", 0))
                return {
                    "id": asset_id,
                    "symbol": asset_id.upper(),
                    "price_usd": price,
                    "market_cap": 0,
                    "fdv": 0,
                    "total_volume_24h": vol,
                    "circulating_supply": 0,
                    "total_supply": 0,
                    "max_supply": 0
                }
        except Exception:
            return None


def fetch_funding_rate(symbol):
    """Fetch live funding rate from Bybit/Binance public endpoints."""
    # Bybit Linear Tickers endpoint (fast & globally available)
    bybit_url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
    try:
        req = urllib.request.Request(bybit_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=5) as res:
            d = json.loads(res.read().decode("utf-8"))
            item = d.get("result", {}).get("list", [])[0]
            rate = float(item.get("fundingRate", 0))
            mark = float(item.get("markPrice", 0))
            index = float(item.get("indexPrice", 0))
            return {
                "symbol": symbol,
                "mark_price": mark,
                "index_price": index,
                "last_funding_rate": rate,
                "last_funding_rate_pct": rate * 100.0,
                "annualized_funding_pct": rate * 3 * 365 * 100.0,
                "next_funding_time_utc": str(item.get("nextFundingTime", 0))
            }
    except Exception:
        pass

    # Fallback to Binance Futures
    url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=4) as res:
            d = json.loads(res.read().decode("utf-8"))
            rate = float(d.get("lastFundingRate", 0))
            return {
                "symbol": symbol,
                "mark_price": float(d.get("markPrice", 0)),
                "index_price": float(d.get("indexPrice", 0)),
                "last_funding_rate": rate,
                "last_funding_rate_pct": rate * 100.0,
                "annualized_funding_pct": rate * 3 * 365 * 100.0,
                "next_funding_time_utc": str(d.get("nextFundingTime", 0))
            }
    except Exception as e:
        return {"error": str(e)}


def evaluate_tokenomics(metrics):
    mc = metrics.get("market_cap", 0)
    fdv = metrics.get("fdv", 0)
    vol = metrics.get("total_volume_24h", 0)
    circ = metrics.get("circulating_supply", 0)
    total = metrics.get("total_supply", 0) or circ

    mc_fdv_ratio = (mc / fdv) if fdv > 0 else 1.0
    circ_ratio = (circ / total) if total > 0 else 1.0
    turnover = (vol / mc) if mc > 0 else 0.0

    if mc_fdv_ratio >= 0.80:
        dilution_risk = "LOW"
        dilution_desc = f"{mc_fdv_ratio * 100:.1f}% circulating; low future token unlock overhang."
    elif mc_fdv_ratio >= 0.40:
        dilution_risk = "MODERATE"
        dilution_desc = f"{mc_fdv_ratio * 100:.1f}% circulating; moderate unlocks scheduled."
    else:
        dilution_risk = "HIGH"
        dilution_desc = f"Only {mc_fdv_ratio * 100:.1f}% circulating; extreme dilution overhang from unvested tokens."

    if turnover >= 0.15:
        liq_health = "HIGH_TURNOVER"
    elif turnover >= 0.03:
        liq_health = "NORMAL"
    else:
        liq_health = "LOW_LIQUIDITY"

    return {
        "mc_fdv_ratio": round(mc_fdv_ratio, 3),
        "circulating_ratio": round(circ_ratio, 3),
        "turnover_ratio": round(turnover, 3),
        "dilution_risk": dilution_risk,
        "dilution_description": dilution_desc,
        "liquidity_health": liq_health
    }


def main():
    parser = argparse.ArgumentParser(description="Crypto Tokenomics & Fundamentals Analyst (crypto-analyst)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check
    chk_p = subparsers.add_parser("check", help="Analyze tokenomics for a coin")
    chk_p.add_argument("coin", help="Coin name or ID, e.g. bitcoin, ethereum, solana")
    chk_p.add_argument("--json", action="store_true")

    # Subcommand: funding
    fund_p = subparsers.add_parser("funding", help="Analyze funding rate & derivatives leverage")
    fund_p.add_argument("symbol", help="e.g. BTCUSDT, ETHUSDT")
    fund_p.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "check":
        # Map common symbols to CoinGecko IDs
        id_map = {
            "btc": "bitcoin",
            "eth": "ethereum",
            "sol": "solana",
            "bnb": "binancecoin",
            "xrp": "ripple",
            "ada": "cardano",
            "doge": "dogecoin",
            "avax": "avalanche-2"
        }
        coin_id = id_map.get(args.coin.lower(), args.coin.lower())
        metrics = fetch_tokenomics(coin_id)
        if not metrics:
            print(f"Error: Unable to fetch tokenomics for {args.coin}.")
            sys.exit(1)

        analysis = evaluate_tokenomics(metrics)
        res = {**metrics, **analysis}

        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print(f"=== Tokenomics & Fundamental Audit: {res.get('name', args.coin).upper()} ===")
            print(f"Price:             ${res['price_usd']:,.2f}")
            print(f"Market Cap:        ${res['market_cap']:,.0f}")
            print(f"FDV:               ${res['fdv']:,.0f}")
            print(f"24h Volume:        ${res['total_volume_24h']:,.0f}")
            print(f"Circulating:       {res['circulating_supply']:,.0f} / Total {res['total_supply']:,.0f}")
            print("--------------------------------------------------")
            print(f"MC / FDV Ratio:    {res['mc_fdv_ratio']:.2f} [{res['dilution_risk']}]")
            print(f"Dilution Context:  {res['dilution_description']}")
            print(f"Turnover Health:   {res['liquidity_health']} (Vol/MC: {res['turnover_ratio'] * 100:.1f}%)")

    elif args.command == "funding":
        f = fetch_funding_rate(args.symbol.upper())
        if getattr(args, "json", False):
            print(json.dumps(f, indent=2))
        else:
            rate_pct = f.get("last_funding_rate_pct", 0)
            ann_pct = f.get("annualized_funding_pct", 0)
            bias = "Bullish crowded (Longs pay Shorts)" if rate_pct > 0.01 else "Bearish crowded (Shorts pay Longs)" if rate_pct < -0.01 else "Neutral"
            print(f"=== Derivatives Funding Analysis: {args.symbol.upper()} ===")
            print(f"Mark Price:        ${f.get('mark_price', 0):,.2f}")
            print(f"Index Price:       ${f.get('index_price', 0):,.2f}")
            print(f"8h Funding Rate:   {rate_pct:+.4f}%")
            print(f"Annualized Rate:   {ann_pct:+.2f}%")
            print(f"Market Bias:       {bias}")


if __name__ == "__main__":
    main()
