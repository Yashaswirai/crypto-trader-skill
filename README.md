# The Crypto Trader Skill Suite

11 modular AI assistant skills engineered specifically for cryptocurrency markets: scan thousands of 24/7 crypto charts, track macro market sentiment, monitor institutional whale tape flow, time high-volume breakouts, and replay every setup through 10,000 Monte Carlo bootstrap simulations before risking capital.

**Free, MIT, no signup, zero API keys required.**
The tools use standard library Python (3.8+) that connects to free, public, rate-limit friendly endpoints:
- **Binance Public REST** (24/7 candles, tickers, order book depth)
- **Alternative.me** (Crypto Fear & Greed sentiment index)
- **Bybit & Binance Futures** (Perpetual funding rates & open interest)
- **CoinGecko & CoinCap** (Circulating supply, FDV, market cap rankings)

Human-in-the-loop safety is enforced across the entire pipeline:
- Paper trading simulation is active by default.
- Orders must pass strict risk checks (max loss per trade, daily loss limit, reward:risk, leverage ceiling).
- The broker executor **never** executes a trade without your explicit confirmation.

---

## The 11 Crypto Skills

| Command | Skill | Responsibility |
| :--- | :--- | :--- |
| `/crypto-scanner` | **Chart Scanner** | Scans 3,000+ liquid USDT crypto pairs for 24h breakouts, session range breakouts (Asian/London/NY), bull flags, and volume surges. |
| `/crypto-news` | **Sentiment & Catalysts** | Real-time Crypto Fear & Greed index, macro market regimes, and 24h momentum catalysts. |
| `/crypto-entry` | **Entry Timer** | Watches 1m, 5m, and 15m bars bar-by-bar; triggers strictly when a completed bar CLOSES above a breakout level with volume confirmation. |
| `/crypto-exit` | **Exit Planner** | Computes stop losses (percentage, 14-bar ATR, or swing lows) and take-profit targets (1R, 2R, 3R); enforces exchange fee and holding window limits. |
| `/crypto-timemachine` | **Time Machine** | Replays 10,000 Monte Carlo bootstrap paths from recent 5m return distributions; outputs win/loss odds and mathematical expectancy in R. |
| `/crypto-budget` | **Position Sizer** | Calculates exact fractional crypto position sizes matching exchange LOT_SIZE filters across 4 risk limits; writes bracket orders. |
| `/crypto-risk` | **Risk Guardian** | Enforces hard risk limits (max loss, cumulative daily loss, leverage ceiling, daily trade count, blacklists); issues signed PASS/BLOCK verdicts. |
| `/crypto-broker` | **Order Executor** | Paper trading simulation engine with live mark-to-market PnL; generates Binance OCO and CCXT REST payloads; requires human confirmation. |
| `/crypto-alerts` | **Alerts & Clocks** | Monitors active stops, targets, global trading session opens (Asian 00:00 UTC, London 08:00 UTC, NY 13:30 UTC), and 8h funding settlement reminders. |
| `/crypto-analyst` | **Tokenomics Auditor** | Computes MC/FDV dilution overhang, circulating supply ratio, volume turnover depth, and derivatives funding bias. |
| `/crypto-whale` | **Whale Tracker** | Scans live exchange tape for institutional block orders (>= $100,000) and calculates net whale accumulation versus distribution delta. |

---

## Typical Trading Workflow

```text
1. /crypto-scanner daily               -> Discovers high-momentum setups (crypto-trader/watchlist.json)
2. /crypto-news watchlist              -> Checks macro Fear & Greed sentiment regime
3. /crypto-whale scan BTCUSDT          -> Verifies institutional whale order-flow delta
4. /crypto-entry check BTCUSDT         -> Confirms completed bar close above breakout level
5. /crypto-exit plan                   -> Sets ATR stop-loss and 2R take-profit (crypto-trader/plan.json)
6. /crypto-timemachine run             -> Replays 10,000 simulations to verify statistical edge
7. /crypto-budget --budget 10000       -> Sizes fractional quantity to max loss limit (crypto-trader/orders.json)
8. /crypto-risk                        -> Audits order against risk ceiling (crypto-trader/state/risk.json)
9. /crypto-broker show                 -> Displays approved ticket card; executes paper fill upon approval
```

---

## Installation

### In Antigravity / Claude Code:
The skills are located under `.agents/skills/crypto-*`. They are automatically discovered and loaded on demand.

### Standalone CLI:
Run any script directly using standard Python 3.8+:
```bash
python3 crypto-scanner/scan.py daily
python3 crypto-news/news.py fng
python3 crypto-timemachine/timemachine.py run
python3 tests/test_crypto_suite.py
```

### Running Tests:
```bash
python3 tests/test_crypto_suite.py
```
All 11 unit and regression tests run completely offline with zero external dependencies.
