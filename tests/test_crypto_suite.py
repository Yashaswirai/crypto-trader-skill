#!/usr/bin/env python3
"""End-to-End Regression & Unit Test Suite for Crypto Trader Skill Suite.
Tests all 11 skills: scanner, news, entry, exit, timemachine, budget, risk, broker, alerts, analyst, whale.
Standard library unittest only, runs offline without external dependencies.
"""

import json
import os
import shutil
import tempfile
import unittest

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _load import load

scan = load("crypto-scanner", "scan")
news = load("crypto-news", "news")
entry = load("crypto-entry", "entry")
c_exit = load("crypto-exit", "exit")
timemachine = load("crypto-timemachine", "timemachine")
size = load("crypto-budget", "size")
check = load("crypto-risk", "check")
ticket = load("crypto-broker", "ticket")
alerts = load("crypto-alerts", "alerts")
analyst = load("crypto-analyst", "analyst")
whale = load("crypto-whale", "whale")


class TestCryptoTraderSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="test_crypto_trader_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_scanner_universe_and_setups(self):
        sample_tickers = [
            {"symbol": "BTCUSDT", "quoteVolume": "50000000", "lastPrice": "80000", "priceChangePercent": "2.5", "highPrice": "80500", "lowPrice": "78000"},
            {"symbol": "ETHUSDT", "quoteVolume": "30000000", "lastPrice": "3200", "priceChangePercent": "8.0", "highPrice": "3220", "lowPrice": "2950"},
            {"symbol": "USDCUSDT", "quoteVolume": "100000000", "lastPrice": "1.0", "priceChangePercent": "0.0", "highPrice": "1.0", "lowPrice": "1.0"},
        ]
        fixture_path = os.path.join(self.test_dir, "tickers.json")
        with open(fixture_path, "w") as f:
            json.dump(sample_tickers, f)

        universe = scan.get_universe(min_volume_usd=10_000_000, offline=fixture_path)
        self.assertEqual(len(universe), 2)
        symbols = [u["symbol"] for u in universe]
        self.assertIn("BTCUSDT", symbols)
        self.assertIn("ETHUSDT", symbols)
        self.assertNotIn("USDCUSDT", symbols)

        hits = scan.scan_daily_setups(symbols="BTCUSDT,ETHUSDT", offline=fixture_path)
        self.assertTrue(len(hits) >= 1)

    def test_02_news_regime_evaluation(self):
        regime, advice = news.evaluate_market_regime(80)
        self.assertEqual(regime, "EXTREME_GREED")
        regime_fear, _ = news.evaluate_market_regime(35)
        self.assertEqual(regime_fear, "FEAR")
        regime_extreme_fear, _ = news.evaluate_market_regime(15)
        self.assertEqual(regime_extreme_fear, "EXTREME_FEAR")

    def test_03_entry_evaluation(self):
        bars = [
            {"open_time": 1000, "close_time": 2000, "open": 100, "high": 105, "low": 98, "close": 102, "volume": 100, "quote_volume": 10000},
            {"open_time": 2000, "close_time": 3000, "open": 102, "high": 108, "low": 101, "close": 107, "volume": 120, "quote_volume": 12000},
            {"open_time": 3000, "close_time": 4000, "open": 107, "high": 115, "low": 106, "close": 114, "volume": 300, "quote_volume": 34000},
        ]
        res = entry.evaluate_entry("TESTUSDT", bars, setup="breakout", level=110.0, min_volume_x=1.2)
        self.assertEqual(res.get("status"), "triggered")
        self.assertEqual(res.get("entry_price"), 114.0)

    def test_04_exit_planning(self):
        plan = c_exit.calculate_plan("BTCUSDT", entry=80000.0, stop_spec="pct:2.0", target_spec="2R")
        self.assertEqual(plan["symbol"], "BTCUSDT")
        self.assertEqual(plan["entry_price"], 80000.0)
        self.assertEqual(plan["stop_loss"], 78400.0)
        self.assertEqual(plan["take_profit"], 83200.0)
        self.assertEqual(plan["reward_to_risk"], 2.0)

        with self.assertRaises(ValueError):
            c_exit.calculate_plan("BTCUSDT", entry=80000.0, stop_spec="price:81000", target_spec="2R")

    def test_05_timemachine_simulation(self):
        closes = [100.0 + (i * 0.1) for i in range(100)]
        sim = timemachine.run_monte_carlo(entry=100.0, stop=98.0, target=104.0, closes=closes, simulations=500)
        self.assertIsNotNone(sim)
        self.assertIn("target_hit_pct", sim)
        self.assertIn("verdict", sim)

    def test_06_budget_position_sizing(self):
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
        order = size.size_position(plan, config)
        self.assertEqual(order["symbol"], "BTCUSDT")
        self.assertEqual(order["side"], "BUY")
        self.assertTrue(order["quantity"] > 0)
        self.assertTrue(order["max_loss_usd"] <= 100.05)

    def test_07_risk_check_pass_and_block(self):
        valid_order = {
            "symbol": "ETHUSDT",
            "side": "BUY",
            "quantity": 0.5,
            "price": 3000.0,
            "stop_loss_price": 2900.0,
            "take_profit_price": 3200.0,
            "max_loss_usd": 50.0,
            "reward_to_risk": 2.0,
            "leverage": 1
        }
        rules = {
            "max_loss_per_trade_usd": 100.0,
            "max_daily_loss_usd": 300.0,
            "min_reward_risk": 1.5,
            "max_trades_per_day": 4,
            "max_leverage": 5,
            "blocked_symbols": ["LUNAUSDT"]
        }
        res_pass = check.verify_order(valid_order, rules, [])
        self.assertEqual(res_pass["verdict"], "PASS")

        invalid_lev = dict(valid_order, leverage=20)
        res_block_lev = check.verify_order(invalid_lev, rules, [])
        self.assertEqual(res_block_lev["verdict"], "BLOCK")

        invalid_sym = dict(valid_order, symbol="LUNAUSDT")
        res_block_sym = check.verify_order(invalid_sym, rules, [])
        self.assertEqual(res_block_sym["verdict"], "BLOCK")

    def test_08_broker_simulation(self):
        order = {
            "symbol": "SOLUSDT",
            "side": "BUY",
            "quantity": 5.0,
            "price": 180.0,
            "stop_loss_price": 175.0,
            "take_profit_price": 190.0,
            "notional_usd": 900.0,
            "max_loss_usd": 25.0,
            "reward_to_risk": 2.0,
            "leverage": 1
        }
        broker_state = os.path.join(self.test_dir, "broker.json")
        port_state = os.path.join(self.test_dir, "portfolio.json")

        fill = ticket.record_broker_fill(order, broker_state, port_state)
        self.assertEqual(fill["symbol"], "SOLUSDT")
        self.assertTrue(fill["fill_id"].startswith("PAPER_"))

        with open(port_state, "r") as f:
            port = json.load(f)
        self.assertEqual(len(port["positions"]), 1)

    def test_09_alerts_plan_evaluation(self):
        plan = {
            "symbol": "BTCUSDT",
            "entry_price": 80000.0,
            "stop_loss": 78000.0,
            "take_profit": 84000.0,
            "side": "LONG"
        }
        quote_stop = {"symbol": "BTCUSDT", "price": 77900.0}
        alerts_list = alerts.check_plan_alerts(plan, quote_stop)
        self.assertTrue(any("STOP LOSS HIT" in a for a in alerts_list))

        quote_tp = {"symbol": "BTCUSDT", "price": 84100.0}
        alerts_tp = alerts.check_plan_alerts(plan, quote_tp)
        self.assertTrue(any("TAKE PROFIT HIT" in a for a in alerts_tp))

    def test_10_analyst_tokenomics(self):
        metrics = {
            "market_cap": 1_000_000_000,
            "fdv": 1_200_000_000,
            "total_volume_24h": 150_000_000,
            "circulating_supply": 800_000_000,
            "total_supply": 1_000_000_000
        }
        eval_res = analyst.evaluate_tokenomics(metrics)
        self.assertEqual(eval_res["dilution_risk"], "LOW")
        self.assertEqual(eval_res["liquidity_health"], "HIGH_TURNOVER")

    def test_11_whale_tape_analysis(self):
        trades = [
            {"p": "80000", "q": "2.0", "m": False, "T": 1600000000000},
            {"p": "80000", "q": "0.1", "m": True, "T": 1600000001000},
            {"p": "80000", "q": "1.5", "m": True, "T": 1600000002000},
        ]
        w = whale.analyze_whale_trades(trades, min_usd=100_000.0)
        self.assertEqual(w["whale_trades_count"], 2)
        self.assertEqual(w["whale_buy_count"], 1)
        self.assertEqual(w["whale_sell_count"], 1)
        self.assertEqual(w["net_whale_flow_usd"], 40000.0)


if __name__ == "__main__":
    unittest.main()
