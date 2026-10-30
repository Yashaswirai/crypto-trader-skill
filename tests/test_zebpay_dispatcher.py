#!/usr/bin/env python3
"""Unit tests for ZebPay Automated Live Dispatcher."""

import hashlib
import json
import os
import shutil
import tempfile
import unittest

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _load import load

z_disp = load("crypto-broker", "zebpay_dispatcher")


class TestZebPayDispatcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="test_zebpay_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_symbol_normalization(self):
        self.assertEqual(z_disp.format_zebpay_symbol("BTCUSDT", "INR"), "BTC-INR")
        self.assertEqual(z_disp.format_zebpay_symbol("BTCUSDT", "USDT"), "BTC-USDT")
        self.assertEqual(z_disp.format_zebpay_symbol("ETH/USDT", "INR"), "ETH-INR")
        self.assertEqual(z_disp.format_zebpay_symbol("SOL-INR", "INR"), "SOL-INR")
        self.assertEqual(z_disp.format_zebpay_symbol("DOGEBUSD", "INR"), "DOGE-INR")

    def test_build_payload_market_and_limit(self):
        market_order = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": 0.05,
            "price": 80000.0,
        }
        p_market = z_disp.build_zebpay_payload(market_order, quote_currency="INR")
        self.assertEqual(p_market["symbol"], "BTC-INR")
        self.assertEqual(p_market["side"], "BUY")
        self.assertEqual(p_market["type"], "MARKET")
        self.assertEqual(p_market["quantity"], "0.05")
        self.assertNotIn("price", p_market)

        limit_order = {
            "symbol": "ETHUSDT",
            "side": "SELL",
            "type": "LIMIT",
            "quantity": 1.5,
            "price": 3000.0,
        }
        # In INR with conversion rate 85
        p_limit_inr = z_disp.build_zebpay_payload(limit_order, quote_currency="INR", inr_rate=85.0)
        self.assertEqual(p_limit_inr["symbol"], "ETH-INR")
        self.assertEqual(p_limit_inr["price"], "255000.00")

        # In USDT
        p_limit_usdt = z_disp.build_zebpay_payload(limit_order, quote_currency="USDT")
        self.assertEqual(p_limit_usdt["symbol"], "ETH-USDT")
        self.assertEqual(p_limit_usdt["price"], "3000")

    def test_auth_headers_hmac(self):
        api_key = "test_key"
        api_secret = "test_secret"
        ts = "1700000000000"
        body = '{"symbol":"BTC-INR"}'
        headers = z_disp.generate_auth_headers(
            api_key=api_key,
            api_secret=api_secret,
            method="POST",
            path="/orders",
            body=body,
            timestamp=ts,
        )
        self.assertEqual(headers["x-auth-apikey"], api_key)
        self.assertEqual(headers["x-auth-timestamp"], ts)
        self.assertTrue(len(headers["x-auth-signature"]) == 64)

    def test_auth_headers_jwt(self):
        jwt_token = "eySAMPLE.JWT.TOKEN"
        headers = z_disp.generate_auth_headers(jwt_token=jwt_token)
        self.assertEqual(headers["Authorization"], f"Bearer {jwt_token}")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_risk_verification(self):
        order = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.01,
            "price": 80000.0,
            "stop_loss_price": 78000.0,
            "take_profit_price": 84000.0,
        }
        fp = z_disp.compute_order_fingerprint(order)

        risk_file = os.path.join(self.test_dir, "test_risk.json")
        # 1. Matching pass
        with open(risk_file, "w", encoding="utf-8") as f:
            json.dump({"verdict": "PASS", "fingerprint": fp}, f)
        ok, msg = z_disp.verify_risk_authorization(order, risk_file)
        self.assertTrue(ok)

        # 2. Tampered fingerprint
        with open(risk_file, "w", encoding="utf-8") as f:
            json.dump({"verdict": "PASS", "fingerprint": "bad_fp"}, f)
        ok, msg = z_disp.verify_risk_authorization(order, risk_file)
        self.assertFalse(ok)
        self.assertIn("modified", msg)

        # 3. Blocked verdict
        with open(risk_file, "w", encoding="utf-8") as f:
            json.dump({"verdict": "BLOCK", "fingerprint": fp, "rejections": ["max daily loss"]}, f)
        ok, msg = z_disp.verify_risk_authorization(order, risk_file)
        self.assertFalse(ok)
        self.assertIn("BLOCKED", msg)

    def test_record_live_fill(self):
        order = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.01,
            "price": 80000.0,
        }
        resp = {"data": {"orderId": "ZEB_99998888"}}
        state_broker = os.path.join(self.test_dir, "broker_live.json")
        port_file = os.path.join(self.test_dir, "portfolio_live.json")

        fill = z_disp.record_live_fill(order, resp, state_broker, port_file)
        self.assertEqual(fill["fill_id"], "ZEB_99998888")
        self.assertEqual(fill["broker"], "ZEBPAY_LIVE")

        with open(port_file, "r", encoding="utf-8") as f:
            port = json.load(f)
        self.assertEqual(len(port["positions"]), 1)
        self.assertEqual(port["positions"][0]["fill_id"], "ZEB_99998888")


if __name__ == "__main__":
    unittest.main()
