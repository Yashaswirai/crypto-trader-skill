#!/usr/bin/env python3
"""Crypto Order Executor & Paper Simulator for crypto-broker.
Displays human-in-the-loop approved tickets and handles paper trading simulation.
Standard library only. NEVER places live orders without explicit user confirmation.

    python3 ticket.py show                           # display approved ticket card
    python3 ticket.py paper --confirm "yes"          # execute paper simulation fill
    python3 ticket.py positions                      # view open paper positions & PnL
    python3 ticket.py payload                        # output Binance / CCXT REST payload

Safety:
  Refuses to execute or display any ticket that does not have a matching PASS verdict
  in crypto-trader/state/risk.json.
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; crypto-trader-skill/1.0; +https://github.com/crypto-trader-skill)"
BINANCE_HOSTS = ("https://data-api.binance.vision", "https://api.binance.com")
DEFAULT_ORDERS_PATH = "crypto-trader/orders.json"
DEFAULT_STATE_RISK_PATH = "crypto-trader/state/risk.json"
DEFAULT_STATE_BROKER_PATH = "crypto-trader/state/broker.json"
DEFAULT_PORTFOLIO_PATH = "crypto-trader/portfolio.json"


def fetch_live_price(symbol):
    """Fetch current market price from public Binance endpoint."""
    headers = {"User-Agent": UA}
    endpoint = f"/api/v3/ticker/price?symbol={symbol}"
    for host in BINANCE_HOSTS:
        try:
            req = urllib.request.Request(f"{host}{endpoint}", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as res:
                d = json.loads(res.read().decode("utf-8"))
                return float(d.get("price", 0))
        except Exception:
            time.sleep(0.1)
    return None


def verify_risk_pass(order, state_risk_path):
    """Ensure order matches a PASS verdict recorded by crypto-risk."""
    if not os.path.exists(state_risk_path):
        return False, "No risk verdict found. Run crypto-risk check first."
    try:
        with open(state_risk_path, "r", encoding="utf-8") as f:
            v = json.load(f)
        if v.get("verdict") != "PASS":
            return False, f"Risk engine blocked this order: {v.get('rejections')}"
        # Fingerprint match
        canonical = f"{order.get('symbol')}:{order.get('side')}:{order.get('quantity')}:{order.get('price')}:{order.get('stop_loss_price')}:{order.get('take_profit_price')}"
        expected_fp = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
        if v.get("fingerprint") != expected_fp:
            return False, "Order was modified after risk check. Re-run crypto-risk."
        return True, "Risk check PASSED."
    except Exception as e:
        return False, f"Error validating risk state: {e}"


def record_broker_fill(order, state_broker_path, portfolio_path):
    """Record simulated fill in state and update local portfolio."""
    os.makedirs(os.path.dirname(state_broker_path), exist_ok=True)
    history = []
    if os.path.exists(state_broker_path):
        try:
            with open(state_broker_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass

    fill_record = dict(order)
    fill_record["fill_time_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fill_record["fill_id"] = f"PAPER_{int(time.time())}"
    history.append(fill_record)

    with open(state_broker_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    # Update portfolio
    portfolio = {"cash_usd": 10000.0, "positions": []}
    if os.path.exists(portfolio_path):
        try:
            with open(portfolio_path, "r", encoding="utf-8") as f:
                portfolio = json.load(f)
        except Exception:
            pass

    portfolio["positions"].append(fill_record)
    with open(portfolio_path, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)

    return fill_record


def build_exchange_payload(order):
    """Format payload according to Binance REST bracket / OCO specifications."""
    return {
        "binance_spot_oco": {
            "symbol": order["symbol"],
            "side": order["side"],
            "quantity": str(order["quantity"]),
            "price": str(order["take_profit_price"]),
            "stopPrice": str(order["stop_loss_price"]),
            "stopLimitPrice": str(order["stop_loss_price"]),
            "stopLimitTimeInForce": "GTC"
        },
        "ccxt_params": {
            "symbol": f"{order['symbol'].replace('USDT', '')}/USDT",
            "type": order["type"].lower(),
            "side": order["side"].lower(),
            "amount": order["quantity"],
            "price": order["price"],
            "params": {
                "stopLossPrice": order["stop_loss_price"],
                "takeProfitPrice": order["take_profit_price"]
            }
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Crypto Order Executor & Broker Simulator (crypto-broker)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: show
    show_p = subparsers.add_parser("show", help="Display verified order ticket")
    show_p.add_argument("--orders", default=DEFAULT_ORDERS_PATH)
    show_p.add_argument("--state-risk", default=DEFAULT_STATE_RISK_PATH)
    show_p.add_argument("--json", action="store_true")

    # Subcommand: paper
    paper_p = subparsers.add_parser("paper", help="Execute simulated paper trade fill")
    paper_p.add_argument("--confirm", help="Must pass --confirm 'yes' to execute")
    paper_p.add_argument("--orders", default=DEFAULT_ORDERS_PATH)
    paper_p.add_argument("--state-risk", default=DEFAULT_STATE_RISK_PATH)
    paper_p.add_argument("--state-broker", default=DEFAULT_STATE_BROKER_PATH)
    paper_p.add_argument("--portfolio", default=DEFAULT_PORTFOLIO_PATH)

    # Subcommand: positions
    pos_p = subparsers.add_parser("positions", help="Inspect open paper trading positions")
    pos_p.add_argument("--portfolio", default=DEFAULT_PORTFOLIO_PATH)

    # Subcommand: payload
    pay_p = subparsers.add_parser("payload", help="Generate Binance/CCXT REST payload")
    pay_p.add_argument("--orders", default=DEFAULT_ORDERS_PATH)

    args = parser.parse_args()

    if args.command in ("show", "paper", "payload"):
        if not os.path.exists(args.orders):
            print(f"Error: Orders file {args.orders} not found.")
            sys.exit(1)
        with open(args.orders, "r", encoding="utf-8") as f:
            order = json.load(f)

        if args.command == "payload":
            print(json.dumps(build_exchange_payload(order), indent=2))
            sys.exit(0)

        ok, msg = verify_risk_pass(order, args.state_risk)
        if not ok:
            print(f"Refusal: Order not verified for execution.\nReason: {msg}")
            sys.exit(1)

        if args.command == "show":
            if getattr(args, "json", False):
                print(json.dumps(order, indent=2))
            else:
                print("==========================================================")
                print("             CRYPTO ORDER TICKET (READY)                 ")
                print("==========================================================")
                print(f"  Symbol:          {order['symbol']} ({order['side']})")
                print(f"  Type:            {order['type']} (Leverage: {order['leverage']}x)")
                print(f"  Quantity:        {order['quantity']} {order['symbol'].replace('USDT', '')}")
                print(f"  Entry Price:     ${order['price']:<10.4f}")
                print(f"  Stop Loss:       ${order['stop_loss_price']:<10.4f}")
                print(f"  Take Profit:     ${order['take_profit_price']:<10.4f}")
                print(f"  Notional Value:  ${order['notional_usd']:<10.2f}")
                print(f"  Max Loss at Stop:${order['max_loss_usd']:<10.2f}")
                print(f"  Reward to Risk:  {order['reward_to_risk']:.2f}R")
                print("----------------------------------------------------------")
                print("  Mode:            PAPER TRADING (Default)")
                print("  Safety:          Risk checks verified. Ready for confirmation.")
                print("  To execute:      python3 ticket.py paper --confirm 'yes'")
                print("==========================================================")

        elif args.command == "paper":
            if args.confirm != "yes":
                print("Execution Refused: Must provide explicit confirmation: --confirm 'yes'")
                sys.exit(1)
            fill = record_broker_fill(order, args.state_broker, args.portfolio)
            print(f"SUCCESS: Simulated paper fill executed!")
            print(f"  Fill ID:   {fill['fill_id']}")
            print(f"  Symbol:    {fill['symbol']} {fill['side']} {fill['quantity']}")
            print(f"  Price:     ${fill['price']}")
            print(f"  Stop/TP:   SL ${fill['stop_loss_price']} | TP ${fill['take_profit_price']}")
            print(f"  Timestamp: {fill['fill_time_utc']}")

    elif args.command == "positions":
        if not os.path.exists(args.portfolio):
            print("No active positions found.")
            sys.exit(0)
        with open(args.portfolio, "r", encoding="utf-8") as f:
            port = json.load(f)
        positions = port.get("positions", [])
        print(f"=== Active Paper Positions ({len(positions)}) ===")
        for p in positions:
            sym = p["symbol"]
            cur = fetch_live_price(sym) or p["price"]
            pnl_usd = (cur - p["price"]) * p["quantity"] if p["side"] == "BUY" else (p["price"] - cur) * p["quantity"]
            pnl_pct = (pnl_usd / p["notional_usd"]) * 100.0 if p["notional_usd"] > 0 else 0.0
            print(f"  {sym:<10} Qty: {p['quantity']:<8} Entry: ${p['price']:<9.2f} Mark: ${cur:<9.2f} PnL: ${pnl_usd:>+7.2f} ({pnl_pct:>+6.2f}%)")


if __name__ == "__main__":
    main()
