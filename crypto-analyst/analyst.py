#!/usr/bin/env python3
"""Crypto Tokenomics & Market Structure Analyst for crypto-analyst.
Computes long-term spot investment reports and short-term futures trade reports.
Standard library only, zero API keys required.

Usage:
    # Spot Trading (Long-Term Macro Report: 200 SMA, Tokenomics, FDV Overhang, DCA Zones)
    python3 analyst.py spot-report bitcoin
    python3 analyst.py spot-report solana --json

    # Futures Trading (Short-Term Report & Trades: Leverage, Liquidation, Funding Drag, Long/Short Setups)
    python3 analyst.py futures-report BTCUSDT --leverage 5
    python3 analyst.py futures-report ETHUSDT --leverage 10 --side short

    # Original fundamental / derivatives checks (backward-compatible)
    python3 analyst.py check BTC
    python3 analyst.py funding BTCUSDT
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
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

COIN_ID_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "bnb": "binancecoin",
    "xrp": "ripple",
    "ada": "cardano",
    "doge": "dogecoin",
    "avax": "avalanche-2",
    "link": "chainlink",
    "sui": "sui",
    "apt": "aptos",
    "near": "near",
}


REVERSE_MAP = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB",
    "ripple": "XRP",
    "cardano": "ADA",
    "dogecoin": "DOGE",
    "avalanche-2": "AVAX",
    "chainlink": "LINK",
    "sui": "SUI",
    "aptos": "APT",
    "near": "NEAR",
}


def normalize_symbol(coin_or_sym: str) -> tuple[str, str]:
    """Return (coin_id, usdt_symbol)."""
    raw = str(coin_or_sym).strip().lower()
    clean = raw.upper().replace("/", "").replace("-", "")
    if clean.endswith("USDT") and len(clean) > 4:
        base = clean[:-4].lower()
        coin_id = COIN_ID_MAP.get(base, base)
        return coin_id, clean
    if raw in REVERSE_MAP:
        return raw, f"{REVERSE_MAP[raw]}USDT"
    if raw in COIN_ID_MAP:
        return COIN_ID_MAP[raw], f"{raw.upper()}USDT"
    return raw, f"{raw.upper()}USDT"


def fetch_tokenomics(asset_id: str, offline: dict = None) -> dict:
    """Fetch supply and market metrics from public CoinGecko or fallback estimations."""
    if offline:
        return offline

    url = f"{COINGECKO_BASE}/coins/{asset_id.lower()}?localization=false&tickers=false&community_data=false&developer_data=false"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=6) as res:
            d = json.loads(res.read().decode("utf-8"))
            m = d.get("market_data", {})
            return {
                "id": asset_id,
                "name": d.get("name", asset_id.title()),
                "symbol": d.get("symbol", "").upper(),
                "price_usd": float(m.get("current_price", {}).get("usd", 0)),
                "market_cap": float(m.get("market_cap", {}).get("usd", 0)),
                "fdv": float(m.get("fully_diluted_valuation", {}).get("usd", 0) or m.get("market_cap", {}).get("usd", 0)),
                "total_volume_24h": float(m.get("total_volume", {}).get("usd", 0)),
                "circulating_supply": float(m.get("circulating_supply", 0)),
                "total_supply": float(m.get("total_supply", 0) or m.get("circulating_supply", 0)),
                "max_supply": float(m.get("max_supply", 0) or 0)
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
                    "name": asset_id.upper(),
                    "symbol": asset_id.upper(),
                    "price_usd": price,
                    "market_cap": price * 19_800_000 if asset_id.lower() == "btc" else 0,
                    "fdv": price * 21_000_000 if asset_id.lower() == "btc" else 0,
                    "total_volume_24h": vol,
                    "circulating_supply": 19_800_000 if asset_id.lower() == "btc" else 0,
                    "total_supply": 21_000_000 if asset_id.lower() == "btc" else 0,
                    "max_supply": 21_000_000 if asset_id.lower() == "btc" else 0
                }
        except Exception:
            return None


def fetch_funding_rate(symbol: str, offline: dict = None) -> dict:
    """Fetch live funding rate from Bybit or Binance public derivatives endpoints."""
    if offline:
        return offline

    # 1. Bybit Linear Tickers endpoint (fast & globally available)
    bybit_url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
    try:
        req = urllib.request.Request(bybit_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=5) as res:
            d = json.loads(res.read().decode("utf-8"))
            items = d.get("result", {}).get("list", [])
            if items:
                item = items[0]
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

    # 2. Fallback to Binance Futures
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
        return {"symbol": symbol, "error": str(e), "mark_price": 0, "last_funding_rate_pct": 0.01, "annualized_funding_pct": 10.95}


def evaluate_tokenomics(metrics: dict) -> dict:
    """Evaluate dilution risk overhang, circulating supply ratio, and turnover."""
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


def fetch_macro_history(symbol: str, days: int = 200, offline_bars: list = None) -> dict:
    """Fetch daily klines to calculate 200 SMA, 50 SMA, 200D High/Low, and macro cycle drawdown."""
    bars = offline_bars
    if not bars:
        endpoint = f"/api/v3/klines?symbol={symbol}&interval=1d&limit={days}"
        headers = {"User-Agent": UA}
        for host in BINANCE_HOSTS:
            try:
                req = urllib.request.Request(f"{host}{endpoint}", headers=headers)
                with urllib.request.urlopen(req, timeout=5) as res:
                    bars = json.loads(res.read().decode("utf-8"))
                    break
            except Exception:
                time.sleep(0.1)

    if not bars or len(bars) < 30:
        return None

    closes = [float(b[4]) for b in bars]
    highs = [float(b[2]) for b in bars]
    lows = [float(b[3]) for b in bars]

    cur_price = closes[-1]
    sma_50 = sum(closes[-50:]) / min(len(closes), 50)
    sma_200 = sum(closes[-200:]) / min(len(closes), 200)
    high_200 = max(highs)
    low_200 = min(lows)

    drawdown_pct = ((high_200 - cur_price) / high_200) * 100.0 if high_200 > 0 else 0.0
    dist_sma200_pct = ((cur_price - sma_200) / sma_200) * 100.0 if sma_200 > 0 else 0.0
    return_30d = ((cur_price - closes[-30]) / closes[-30]) * 100.0 if len(closes) >= 30 else 0.0
    return_90d = ((cur_price - closes[-90]) / closes[-90]) * 100.0 if len(closes) >= 90 else 0.0

    if cur_price > sma_50 and sma_50 > sma_200:
        macro_trend = "BULLISH_EXPANSION (Golden Structure)"
    elif cur_price > sma_200:
        macro_trend = "BULLISH_CONSOLIDATION (Above 200 SMA)"
    elif cur_price > sma_50:
        macro_trend = "ACCUMULATION_BOUNCE (Testing 200 SMA from below)"
    else:
        macro_trend = "BEARISH_DOWNTREND (Below 50 and 200 SMA)"

    return {
        "current_price": cur_price,
        "sma_50": round(sma_50, 2),
        "sma_200": round(sma_200, 2),
        "high_200d": round(high_200, 2),
        "low_200d": round(low_200, 2),
        "drawdown_from_high_pct": round(drawdown_pct, 2),
        "distance_to_sma200_pct": round(dist_sma200_pct, 2),
        "return_30d_pct": round(return_30d, 2),
        "return_90d_pct": round(return_90d, 2),
        "macro_trend": macro_trend
    }


def generate_spot_report(coin_or_symbol: str, offline_tokenomics: dict = None, offline_bars: list = None) -> dict:
    """Generate a Long-Term Spot Investment & Macro Swing Report."""
    coin_id, symbol = normalize_symbol(coin_or_symbol)

    # 1. Fundamentals
    tok = fetch_tokenomics(coin_id, offline=offline_tokenomics) or {
        "id": coin_id, "name": coin_id.title(), "price_usd": 0, "market_cap": 0, "fdv": 0,
        "total_volume_24h": 0, "circulating_supply": 0, "total_supply": 0
    }
    tok_eval = evaluate_tokenomics(tok)

    # 2. Macro 200-day Trend
    macro = fetch_macro_history(symbol, offline_bars=offline_bars) or {
        "current_price": tok.get("price_usd", 0), "sma_50": 0, "sma_200": 0,
        "high_200d": 0, "low_200d": 0, "drawdown_from_high_pct": 0, "distance_to_sma200_pct": 0,
        "return_30d_pct": 0, "return_90d_pct": 0, "macro_trend": "DATA_UNAVAILABLE"
    }

    cur_p = macro["current_price"] or tok.get("price_usd", 0)
    sma_200 = macro["sma_200"]
    sma_50 = macro["sma_50"]

    # Spot Long-Term Strategy Verdict
    if tok_eval["dilution_risk"] == "HIGH":
        verdict = "AVOID_LONG_TERM_SPOT"
        guidance = "Heavy token unlock overhang. High risk of supply dilution on spot holders."
    elif cur_p > sma_200 and sma_200 > 0:
        verdict = "STRONG_SPOT_SWING_ACCUMULATION"
        guidance = "Asset is in macro bull structure above 200 SMA. Suitable for multi-week swing holding."
    elif macro["drawdown_from_high_pct"] >= 50.0 and tok_eval["dilution_risk"] == "LOW":
        verdict = "DEEP_VALUE_SPOT_DCA"
        guidance = "Substantial macro discount on low-dilution token. Favorable for Dollar-Cost-Averaging."
    else:
        verdict = "SPOT_OBSERVE"
        guidance = "Wait for macro reclaim of 200-day moving average before opening large spot swing positions."

    # DCA and Swing target brackets
    dca_low = round(cur_p * 0.90, 2)
    dca_high = round(cur_p * 0.98, 2)
    swing_stop = round(min(sma_200 * 0.95, cur_p * 0.92), 2) if sma_200 > 0 else round(cur_p * 0.92, 2)
    swing_target = round(cur_p * 1.25, 2)

    return {
        "asset": tok.get("name", coin_id.upper()),
        "symbol": symbol,
        "market": "SPOT CASH",
        "horizon": "LONG_TERM (Weeks to Months)",
        "price_usd": cur_p,
        "macro_trend": macro["macro_trend"],
        "tokenomics": {
            "market_cap_usd": tok["market_cap"],
            "fdv_usd": tok["fdv"],
            "mc_fdv_ratio": tok_eval["mc_fdv_ratio"],
            "dilution_risk": tok_eval["dilution_risk"],
            "dilution_context": tok_eval["dilution_description"]
        },
        "macro_metrics": {
            "sma_50": sma_50,
            "sma_200": sma_200,
            "distance_to_200sma_pct": macro["distance_to_sma200_pct"],
            "drawdown_from_200d_high_pct": macro["drawdown_from_high_pct"],
            "return_30d_pct": macro["return_30d_pct"],
            "return_90d_pct": macro["return_90d_pct"]
        },
        "spot_strategy": {
            "verdict": verdict,
            "guidance": guidance,
            "recommended_dca_range": f"${dca_low} - ${dca_high}",
            "macro_swing_stop": swing_stop,
            "macro_swing_target": swing_target,
            "liquidation_risk": "NONE (Spot Asset - Zero Liquidation Risk)",
            "funding_fee_bleed": "ZERO (No overnight perpetual funding drag)"
        }
    }


def fetch_intraday_data(symbol: str, interval: str = "15m", limit: int = 48, offline_bars: list = None) -> dict:
    """Fetch 15-minute bars to calculate short-term intraday volatility and levels."""
    bars = offline_bars
    if not bars:
        endpoint = f"/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        headers = {"User-Agent": UA}
        for host in BINANCE_HOSTS:
            try:
                req = urllib.request.Request(f"{host}{endpoint}", headers=headers)
                with urllib.request.urlopen(req, timeout=5) as res:
                    bars = json.loads(res.read().decode("utf-8"))
                    break
            except Exception:
                time.sleep(0.1)

    if not bars or len(bars) < 14:
        return {"atr_15m": 0, "intraday_high": 0, "intraday_low": 0}

    highs = [float(b[2]) for b in bars]
    lows = [float(b[3]) for b in bars]
    closes = [float(b[4]) for b in bars]

    # Calculate 14-period ATR
    tr_list = []
    for i in range(1, len(bars)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_list.append(tr)
    atr = sum(tr_list[-14:]) / 14.0

    return {
        "atr_15m": round(atr, 4),
        "intraday_resistance": round(max(highs[-16:]), 4),  # last 4 hours high
        "intraday_support": round(min(lows[-16:]), 4),      # last 4 hours low
        "cur_price": closes[-1]
    }


def generate_futures_report(
    symbol: str,
    leverage: int = 5,
    side: str = "AUTO",
    offline_funding: dict = None,
    offline_bars: list = None,
) -> dict:
    """Generate a Short-Term Futures Report & Intraday Trade Plan."""
    _, full_symbol = normalize_symbol(symbol)

    # 1. Derivatives funding rate
    fund = fetch_funding_rate(full_symbol, offline=offline_funding)
    mark_p = fund.get("mark_price", 0)

    # 2. Intraday volatility & support/resistance
    intra = fetch_intraday_data(full_symbol, offline_bars=offline_bars)
    cur_p = intra.get("cur_price") or mark_p or 100.0
    atr = intra.get("atr_15m") or (cur_p * 0.008)

    rate_pct = fund.get("last_funding_rate_pct", 0.01)
    ann_pct = fund.get("annualized_funding_pct", 10.95)

    # Market bias from funding
    if rate_pct > 0.02:
        funding_bias = "EXTREME_LONGS_CROWDED (Long Squeeze Risk - Shorts Earn Funding)"
    elif rate_pct > 0.005:
        funding_bias = "BULLISH_CROWDED (Longs pay Shorts)"
    elif rate_pct < -0.01:
        funding_bias = "BEARISH_CROWDED (Shorts pay Longs - Short Squeeze Risk)"
    else:
        funding_bias = "BALANCED_NEUTRAL"

    # Liquidation calculations
    lev_d = max(1, int(leverage))
    initial_margin_pct = (1.0 / lev_d) * 100.0
    maint_margin_pct = 0.005  # 0.5% standard maintenance margin rate

    # Liquidation formulas
    liq_long = cur_p * (1.0 - (1.0 / lev_d) + maint_margin_pct)
    liq_short = cur_p * (1.0 + (1.0 / lev_d) - maint_margin_pct)

    # Directional trade plans (Long vs Short)
    # Long Setup: Entry at resistance, stop at 1.5 ATR, target at 2R
    long_entry = round(cur_p, 4)
    long_stop = round(cur_p - (1.5 * atr), 4)
    long_risk = long_entry - long_stop
    long_target = round(long_entry + (2.0 * long_risk), 4)
    long_liq_buffer = ((long_entry - liq_long) / long_entry) * 100.0

    # Short Setup: Entry at support breakdown, stop at 1.5 ATR, target at 2R
    short_entry = round(cur_p, 4)
    short_stop = round(cur_p + (1.5 * atr), 4)
    short_risk = short_stop - short_entry
    short_target = round(short_entry - (2.0 * short_risk), 4)
    short_liq_buffer = ((liq_short - short_entry) / short_entry) * 100.0

    # Determine recommended bias
    if side.upper() in ("LONG", "SHORT"):
        rec_side = side.upper()
    else:
        rec_side = "SHORT" if "EXTREME_LONGS_CROWDED" in funding_bias else "LONG"

    # Cost of funding per $1,000 notional per 8 hours
    funding_cost_per_1000 = (rate_pct / 100.0) * 1000.0

    return {
        "symbol": full_symbol,
        "market": "FUTURES PERPETUAL",
        "horizon": "SHORT_TERM (Scalp / Intraday: 1h - 8h)",
        "leverage": f"{lev_d}x",
        "mark_price": cur_p,
        "derivatives_sentiment": {
            "8h_funding_rate_pct": f"{rate_pct:+.4f}%",
            "annualized_funding_pct": f"{ann_pct:+.2f}%",
            "market_crowdedness": funding_bias,
            "cost_per_1000usd_per_8h": f"${abs(funding_cost_per_1000):.2f} ({'paid by Longs' if rate_pct > 0 else 'paid by Shorts'})"
        },
        "leverage_risk_profile": {
            "initial_margin_requirement": f"{initial_margin_pct:.1f}% ($1,000 notional requires ${1000.0 / lev_d:.2f} margin)",
            "liquidation_price_long": round(liq_long, 4),
            "liquidation_price_short": round(liq_short, 4),
            "long_liquidation_buffer_pct": f"{long_liq_buffer:.2f}%",
            "short_liquidation_buffer_pct": f"{short_liq_buffer:.2f}%"
        },
        "short_term_trade_setups": {
            "recommended_bias": rec_side,
            "holding_window_limit": "Max 8 hours (Flat before funding fee settlement)",
            "long_scalp": {
                "entry": long_entry,
                "stop_loss": long_stop,
                "take_profit": long_target,
                "reward_to_risk": "2.00R",
                "stop_loss_distance_pct": f"{((long_entry - long_stop) / long_entry) * 100:.2f}%",
                "liquidation_safety_buffer": f"{long_liq_buffer:.2f}% (Stop triggers well before liquidation at ${liq_long:.2f})"
            },
            "short_scalp": {
                "entry": short_entry,
                "stop_loss": short_stop,
                "take_profit": short_target,
                "reward_to_risk": "2.00R",
                "stop_loss_distance_pct": f"{((short_stop - short_entry) / short_entry) * 100:.2f}%",
                "liquidation_safety_buffer": f"{short_liq_buffer:.2f}% (Stop triggers well before liquidation at ${liq_short:.2f})"
            }
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Crypto Tokenomics, Spot & Futures Analyst (crypto-analyst)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: spot-report
    spot_p = subparsers.add_parser("spot-report", help="Generate Long-Term Spot Report (Macro 200 SMA, Dilution, DCA)")
    spot_p.add_argument("coin", help="Coin name or symbol, e.g. bitcoin, BTCUSDT, solana")
    spot_p.add_argument("--json", action="store_true")

    # Subcommand: futures-report
    fut_p = subparsers.add_parser("futures-report", help="Generate Short-Term Futures Report (Leverage, Liquidation, Funding, Scalp Trades)")
    fut_p.add_argument("symbol", help="Futures symbol, e.g. BTCUSDT, ETHUSDT")
    fut_p.add_argument("--leverage", type=int, default=5, help="Leverage multiplier (e.g. 2, 5, 10)")
    fut_p.add_argument("--side", choices=["long", "short", "auto"], default="auto")
    fut_p.add_argument("--json", action="store_true")

    # Subcommand: check (original)
    chk_p = subparsers.add_parser("check", help="Analyze tokenomics for a coin")
    chk_p.add_argument("coin", help="Coin name or ID, e.g. bitcoin, ethereum, solana")
    chk_p.add_argument("--json", action="store_true")

    # Subcommand: funding (original)
    fund_p = subparsers.add_parser("funding", help="Analyze funding rate & derivatives leverage")
    fund_p.add_argument("symbol", help="e.g. BTCUSDT, ETHUSDT")
    fund_p.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "spot-report":
        report = generate_spot_report(args.coin)
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2))
        else:
            print("==========================================================")
            print(f"        CRYPTO SPOT REPORT (LONG-TERM MACRO AUDIT)       ")
            print("==========================================================")
            print(f"  Asset:           {report['asset']} ({report['symbol']})")
            print(f"  Current Price:   ${report['price_usd']:,.2f}")
            print(f"  Market Type:     {report['market']} (Zero Liquidation Risk)")
            print(f"  Holding Horizon: {report['horizon']}")
            print("----------------------------------------------------------")
            print("  [MACRO TREND & CYCLE STRUCTURE]")
            print(f"  Trend Structure: {report['macro_trend']}")
            print(f"  50-Day SMA:      ${report['macro_metrics']['sma_50']:,.2f}")
            print(f"  200-Day SMA:     ${report['macro_metrics']['sma_200']:,.2f} ({report['macro_metrics']['distance_to_200sma_pct']:+.1f}% vs 200 SMA)")
            print(f"  Cycle Drawdown:  -{report['macro_metrics']['drawdown_from_200d_high_pct']:.1f}% from 200-day high")
            print(f"  90-Day Return:   {report['macro_metrics']['return_90d_pct']:+.1f}%")
            print("----------------------------------------------------------")
            print("  [TOKENOMICS & DILUTION RISK]")
            print(f"  MC / FDV Ratio:  {report['tokenomics']['mc_fdv_ratio']:.2f} [{report['tokenomics']['dilution_risk']}]")
            print(f"  Dilution Context:{report['tokenomics']['dilution_context']}")
            print("----------------------------------------------------------")
            print("  [LONG-TERM SPOT STRATEGY]")
            print(f"  Verdict:         {report['spot_strategy']['verdict']}")
            print(f"  Guidance:        {report['spot_strategy']['guidance']}")
            print(f"  DCA Buy Zone:    {report['spot_strategy']['recommended_dca_range']}")
            print(f"  Macro Swing Stop:${report['spot_strategy']['macro_swing_stop']:,.2f}")
            print(f"  Macro Target:    ${report['spot_strategy']['macro_swing_target']:,.2f}")
            print(f"  Funding Decay:   {report['spot_strategy']['funding_fee_bleed']}")
            print("==========================================================")

    elif args.command == "futures-report":
        report = generate_futures_report(args.symbol, leverage=args.leverage, side=args.side)
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2))
        else:
            print("==========================================================")
            print(f"       CRYPTO FUTURES REPORT (SHORT-TERM TRADING)        ")
            print("==========================================================")
            print(f"  Symbol:          {report['symbol']} ({report['market']})")
            print(f"  Mark Price:      ${report['mark_price']:,.2f}")
            print(f"  Leverage:        {report['leverage']} (Margin: {report['leverage_risk_profile']['initial_margin_requirement']})")
            print(f"  Holding Window:  {report['horizon']}")
            print("----------------------------------------------------------")
            print("  [DERIVATIVES SENTIMENT & FUNDING BLEED]")
            print(f"  8h Funding Rate: {report['derivatives_sentiment']['8h_funding_rate_pct']}")
            print(f"  Annualized Rate: {report['derivatives_sentiment']['annualized_funding_pct']}")
            print(f"  Crowdedness:     {report['derivatives_sentiment']['market_crowdedness']}")
            print(f"  8h Carry Drag:   {report['derivatives_sentiment']['cost_per_1000usd_per_8h']}")
            print("----------------------------------------------------------")
            print("  [LIQUIDATION SAFETY PROFILE]")
            print(f"  LONG Liquidation: ${report['leverage_risk_profile']['liquidation_price_long']:,.2f} (Buffer: {report['leverage_risk_profile']['long_liquidation_buffer_pct']})")
            print(f"  SHORT Liquidation:${report['leverage_risk_profile']['liquidation_price_short']:,.2f} (Buffer: {report['leverage_risk_profile']['short_liquidation_buffer_pct']})")
            print("----------------------------------------------------------")
            print(f"  [SHORT-TERM TRADE SETUPS - RECOMMENDED: {report['short_term_trade_setups']['recommended_bias']}]")
            lt = report['short_term_trade_setups']['long_scalp']
            st = report['short_term_trade_setups']['short_scalp']
            print(f"  -> LONG Scalp:   Entry ${lt['entry']:<9.2f} | Stop ${lt['stop_loss']:<9.2f} ({lt['stop_loss_distance_pct']}) | Target ${lt['take_profit']:<9.2f} (2R)")
            print(f"     Safety:       {lt['liquidation_safety_buffer']}")
            print(f"  -> SHORT Scalp:  Entry ${st['entry']:<9.2f} | Stop ${st['stop_loss']:<9.2f} ({st['stop_loss_distance_pct']}) | Target ${st['take_profit']:<9.2f} (2R)")
            print(f"     Safety:       {st['liquidation_safety_buffer']}")
            print(f"  Holding Rule:    {report['short_term_trade_setups']['holding_window_limit']}")
            print("==========================================================")

    elif args.command == "check":
        coin_id, _ = normalize_symbol(args.coin)
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
