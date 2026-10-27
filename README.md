# The Crypto Trader skill

11 Claude skills for crypto day trading: scan thousands of charts, track breaking sentiment, time every entry and exit, and replay every outcome before you risk a dollar.

Free, MIT, no signup, zero API keys required. The tools are plain Python standard library that connect to free public endpoints: Binance public REST (24/7 candles, tickers, order book depth), Alternative.me (Crypto Fear & Greed Index), and CoinGecko (circulating supply, FDV).

One scans thousands of 24/7 charts for setups. Another tracks macro crypto sentiment and fear/greed cycles. One monitors institutional whale order tape flow. One watches a setup bar by bar and tells you the moment to get in, and another sets your stop and your target before you do. And the Time Machine replays the setup 10,000 times using Monte Carlo simulation from recent 5-minute candles, giving you honest statistical odds before risking capital.

And no trade goes through until you say yes. Nothing in this pack can place an order on its own. Paper trading is the default.

---

## Install

Paste this into Claude:

```
https://github.com/Yashaswirai/crypto-trader-skill

install skill
```

Or as a plugin, in Claude Code:

```
/plugin marketplace add Yashaswirai/crypto-trader-skill
/plugin install crypto-trader-skill@crypto-trader-skill
```

Claude Code namespaces plugin skills, so installed as a plugin they show up as
`/crypto-trader-skill:crypto-scanner` and so on. Copy the folders instead if you want
plain `/crypto-scanner`:

```bash
git clone https://github.com/Yashaswirai/crypto-trader-skill.git
cp -r crypto-trader-skill/crypto-* ~/.claude/skills/
```

Or run the self-installer:

```bash
python3 crypto-trader-skill/install.py
```

Project-local instead of global: copy the same folders into your repo's
`.claude/skills/` or `.agents/skills/`:

```bash
python3 crypto-trader-skill/install.py --local
# or
python3 crypto-trader-skill/install.py --agents
```

No Claude Code at all? Paste any single `SKILL.md` at the top of a chat and it runs as a mode. You lose the Python tools, but the method works.

The tools need Python 3.8 or newer. Zero pip packages required (100% standard library).

---

## The eleven

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

## How to use it

Everything lands in a `crypto-trader/` folder in your project, and each skill reads what the last one wrote:

```text
scanner -> news -> whale -> entry -> exit -> timemachine -> budget -> risk -> broker   (one trade)
alerts: stop, target, funding settlement, session opens                                (while open)
news / analyst / whale                                                                  (on demand)
```

### Complete Trade Walkthrough

1. **`/crypto-scanner`** finds liquid breakout candidates:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scan.py" daily
   ```
   Writes `crypto-trader/watchlist.json`.

2. **`/crypto-news`** checks current sentiment regime:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/news.py" watchlist
   ```
   Ensures the market is not in Extreme Fear trap conditions.

3. **`/crypto-whale`** verifies smart money flow:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/whale.py" scan BTCUSDT
   ```
   Confirms net institutional buyer demand.

4. **`/crypto-entry`** monitors price bar-by-bar:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/entry.py" check BTCUSDT --level 80500 --interval 5m
   ```
   Triggers only when a bar **closes** above the level. Writes `crypto-trader/entry.json`.

5. **`/crypto-exit`** plans the brackets:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/exit.py" plan --stop atr:1.5 --target 2R
   ```
   Writes `crypto-trader/plan.json`.

6. **`/crypto-timemachine`** stress-tests the odds:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run
   ```
   Replays 10,000 Monte Carlo paths using the token's recent 5-minute volatility to calculate win/loss probabilities and mathematical expectancy in R.

7. **`/crypto-budget`** sizes the position:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/size.py" --budget 10000 --max-loss 100 --write
   ```
   Rounds fractional lots to the exchange step size. Writes `crypto-trader/orders.json`.

8. **`/crypto-risk`** audits safety rules:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/check.py"
   ```
   Issues a cryptographic PASS or BLOCK verdict to `crypto-trader/state/risk.json`.

9. **`/crypto-broker`** formats ticket and simulates fill:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/ticket.py" show
   python3 "${CLAUDE_SKILL_DIR}/ticket.py" paper --confirm "yes"
   ```
   Displays position in `crypto-trader/portfolio.json`.

10. **`/crypto-alerts`** rings when prices or clocks hit:
    ```bash
    python3 "${CLAUDE_SKILL_DIR}/alerts.py" plan
    python3 "${CLAUDE_SKILL_DIR}/alerts.py" sessions
    ```

---

## Running Tests

All tests run completely offline with zero external network or pip dependencies:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## Safety & Disclaimer

Not financial advice. Cryptocurrency trading involves substantial risk of financial loss. These skills are automated analytical tools designed for educational and paper-trading purposes. Always conduct independent research and maintain strict risk parameters before trading live assets.
