---
name: crypto-news
description: >-
  Crypto Sentiment & News Monitor. Tracks crypto macro market sentiment using the
  Alternative.me Fear & Greed Index, monitors 24h market momentum shifts, and attaches
  macro context to candidates in crypto-trader/watchlist.json. Free public endpoints,
  zero API keys required.
argument-hint: "[fng | watchlist | check <symbols>]"
---

# crypto-news

The Crypto News and Sentiment Monitor tracks market psychology and sentiment regimes.
In crypto, market sentiment strongly dictates whether breakout setups follow through
(Greed/Extreme Greed) or form liquidity traps (Fear/Extreme Fear).

```bash
# Check current Crypto Fear & Greed Index
python3 crypto-news/news.py fng

# View 14-day sentiment trend
python3 crypto-news/news.py fng --history 14

# Check sentiment and catalysts for symbols in the active watchlist
python3 crypto-news/news.py watchlist

# Check specific tokens
python3 crypto-news/news.py check BTCUSDT,SOLUSDT
```
