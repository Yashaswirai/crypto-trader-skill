---
name: crypto-scanner
description: >-
  Crypto Market Scanner. Scans thousands of 24/7 crypto pairs across liquid USDT markets
  for high-probability setups: 24h high breakouts, session range breakouts (Asian, London,
  and New York sessions), volume surges, and oversold bounces. Writes crypto-trader/watchlist.json
  for downstream entry and risk checking. Standard library Python, zero API keys required.
argument-hint: "[universe | daily | session] [--symbols BTCUSDT,...] [--min-volume USD]"
---

# crypto-scanner

The Crypto Scanner is the discovery engine of the crypto trading workflow.
It reads 24/7 cryptocurrency market data from free public endpoints and identifies
trading pairs matching explicit mathematical criteria.

```bash
# Discover top liquid USDT crypto pairs
python3 crypto-scanner/scan.py universe --min-volume 10000000

# Run 24-hour setup scan (breakouts, flags, surges)
python3 crypto-scanner/scan.py daily

# Scan specific focus coins
python3 crypto-scanner/scan.py daily --symbols BTCUSDT,ETHUSDT,SOLUSDT

# Scan for London session range breakouts from the Asian range
python3 crypto-scanner/scan.py session --session london
```

Outputs:
- `crypto-trader/universe.txt`
- `crypto-trader/watchlist.json`
