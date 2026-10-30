#!/usr/bin/env python3
"""Unit tests for Spot (Long-Term) vs Futures (Short-Term) reporting & sizing."""

import json
import os
import shutil
import tempfile
import unittest

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _load import load

analyst = load("crypto-analyst", "analyst")
size = load("crypto-budget", "size")
scan = load("crypto-scanner", "scan")


class TestSpotFuturesCapabilities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="test_spot_fut_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_spot_longterm_report(self):
        # Offline tokenomics fixture
        tokenomics_fixture = {
            "id": "bitcoin",
            "name": "Bitcoin",
            "symbol": "BTC",
            "price_usd": 80000.0,
            "market_cap": 1_500_000_000_000,
            "fdv": 1_680_000_000_000,
            "total_volume_24h": 30_000_000_000,
            "circulating_supply": 19_800_000,
            "total_supply": 21_000_000,
            "max_supply": 21_000_000
        }
        # 200 synthetic daily bars (uptrend from 60k to 80k)
        daily_bars = []
        for i in range(200):
            p = 60000.0 + (i * 100.0)
            daily_bars.append([i, p - 100, p + 200, p - 200, p, 1000])

        rep = analyst.generate_spot_report("bitcoin", offline_tokenomics=tokenomics_fixture, offline_bars=daily_bars)
        self.assertEqual(rep["market"], "SPOT CASH")
        self.assertIn("LONG_TERM", rep["horizon"])
        self.assertEqual(rep["spot_strategy"]["liquidation_risk"], "NONE (Spot Asset - Zero Liquidation Risk)")
        self.assertTrue(rep["macro_metrics"]["sma_200"] > 0)
        self.assertTrue(rep["macro_metrics"]["sma_50"] > rep["macro_metrics"]["sma_200"])

    def test_futures_shortterm_report(self):
        funding_fixture = {
            "symbol": "BTCUSDT",
            "mark_price": 80000.0,
            "index_price": 80010.0,
            "last_funding_rate": 0.0001,
            "last_funding_rate_pct": 0.01,
            "annualized_funding_pct": 10.95
        }
        bars_15m = []
        for i in range(48):
            p = 80000.0 + (i * 10.0)
            bars_15m.append([i, p, p + 50, p - 50, p, 100])

        rep = analyst.generate_futures_report("BTCUSDT", leverage=5, offline_funding=funding_fixture, offline_bars=bars_15m)
        self.assertEqual(rep["market"], "FUTURES PERPETUAL")
        self.assertIn("SHORT_TERM", rep["horizon"])
        self.assertEqual(rep["leverage"], "5x")
        self.assertTrue("initial_margin_requirement" in rep["leverage_risk_profile"])
        # Liquidation price for 5x long at 80k should be around 64k
        liq_long = rep["leverage_risk_profile"]["liquidation_price_long"]
        self.assertTrue(60000.0 < liq_long < 70000.0)
        # Scalp trades exist for both sides
        self.assertIn("long_scalp", rep["short_term_trade_setups"])
        self.assertIn("short_scalp", rep["short_term_trade_setups"])

    def test_budget_spot_vs_futures_sizing(self):
        plan = {
            "symbol": "BTCUSDT",
            "entry_price": 80000.0,
            "stop_loss": 78000.0,
            "take_profit": 84000.0,
            "reward_to_risk": 2.0,
            "side": "LONG"
        }
        config = {
            "budget_usd": 10000.0,
            "max_loss_per_trade_usd": 100.0,
            "max_position_pct": 0.25,
            "max_order_usd": 2500.0,
            "cash_buffer_pct": 0.10,
            "min_order_usd": 10.0
        }

        # Spot sizing (1x leverage)
        order_spot = size.size_position(plan, config, leverage=1)
        self.assertEqual(order_spot["market_type"], "SPOT")
        self.assertIn("LONG_TERM", order_spot["horizon"])
        self.assertIsNone(order_spot["liquidation_price"])

        # Futures sizing (5x leverage)
        order_fut = size.size_position(plan, config, leverage=5)
        self.assertEqual(order_fut["market_type"], "FUTURES")
        self.assertIn("SHORT_TERM", order_fut["horizon"])
        self.assertIsNotNone(order_fut["liquidation_price"])
        self.assertTrue(order_fut["liquidation_price"] < order_fut["stop_loss_price"])
        self.assertTrue(order_fut["margin_usd"] < order_fut["notional_usd"])

    def test_dangerous_futures_liquidation_rejected(self):
        # Stop loss past liquidation price should raise ValueError
        bad_plan = {
            "symbol": "BTCUSDT",
            "entry_price": 80000.0,
            "stop_loss": 60000.0,  # 5x liquidation is ~64k, stop at 60k is past liquidation
            "take_profit": 120000.0,
            "side": "LONG"
        }
        config = {
            "budget_usd": 10000.0,
            "max_loss_per_trade_usd": 5000.0,
            "max_position_pct": 0.50,
            "max_order_usd": 5000.0,
            "cash_buffer_pct": 0.10,
            "min_order_usd": 10.0
        }
        with self.assertRaises(ValueError) as ctx:
            size.size_position(bad_plan, config, leverage=5)
        self.assertIn("Dangerous Futures Setup", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
