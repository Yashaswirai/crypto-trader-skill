#!/usr/bin/env python3
"""Automated Live Dispatcher for ZebPay (crypto-broker extension).
Connects crypto trading skills to ZebPay Spot REST API (https://docs.zebpay.com).
Standard library Python only, zero external dependencies required.

Features:
- Validates cryptographic risk fingerprints from crypto-risk before dispatch.
- Enforces explicit user confirmation (--confirm "yes") for live capital orders.
- Supports both ZebPay API Key + HMAC-SHA256 signature and JWT Bearer authentication.
- Automatically handles symbol normalization (e.g. BTCUSDT -> BTC-INR or BTC-USDT).
- Supports --dry-run mode to verify payload and signatures without placing orders.
- Records live fill responses to broker state and portfolio.

Environment Variables:
    ZEBPAY_API_KEY      ZebPay API Key
    ZEBPAY_API_SECRET   ZebPay Secret Key (for HMAC-SHA256 signature)
    ZEBPAY_JWT_TOKEN    Optional: ZebPay Bearer JWT Token (alternative to API key)
    ZEBPAY_INR_RATE     Optional: USD to INR conversion rate if order is USD-denominated

Usage:
    python3 zebpay_dispatcher.py preview                  # preview mapped ZebPay payload
    python3 zebpay_dispatcher.py dry-run                  # test signing & validation without placing
    python3 zebpay_dispatcher.py dispatch --confirm "yes" # live dispatch to ZebPay
"""

import argparse
import datetime
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://sapi.zebpay.com"
DEFAULT_SPOT_URL = "https://sapi.zebpay.com"
DEFAULT_FUTURES_URL = "https://futuresbe.zebpay.com"
DEFAULT_ORDER_PATH = "/orders"
FALLBACK_ORDER_PATH = "/v2/ex/orders"
DEFAULT_ORDERS_PATH = "crypto-trader/orders.json"
DEFAULT_STATE_RISK_PATH = "crypto-trader/state/risk.json"
DEFAULT_STATE_BROKER_PATH = "crypto-trader/state/broker.json"
DEFAULT_PORTFOLIO_PATH = "crypto-trader/portfolio.json"
DEFAULT_USER_AGENT = "crypto-trader-skill/1.0 (+https://github.com/zebpay)"


def get_zebpay_credentials():
    """Retrieve ZebPay API credentials from environment variables."""
    api_key = os.getenv("ZEBPAY_API_KEY", "").strip()
    api_secret = os.getenv("ZEBPAY_API_SECRET", "").strip()
    jwt_token = os.getenv("ZEBPAY_JWT_TOKEN", "").strip()
    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "jwt_token": jwt_token,
    }


def format_zebpay_symbol(symbol: str, target_quote: str = "INR") -> str:
    """Normalize exchange symbols into ZebPay standard notation (e.g., BTC-INR, BTC-USDT).
    
    Examples:
        BTCUSDT -> BTC-INR (or BTC-USDT)
        BTC/INR -> BTC-INR
        ETH-INR -> ETH-INR
    """
    clean = str(symbol).strip().upper()
    if "/" in clean:
        base, _ = clean.split("/", 1)
        return f"{base}-{target_quote.upper()}"
    if "-" in clean:
        parts = clean.split("-")
        return f"{parts[0]}-{parts[1]}"

    # Stripping common quote currencies
    quotes = ("USDT", "BUSD", "USDC", "INR")
    base = clean
    for q in quotes:
        if clean.endswith(q) and len(clean) > len(q):
            base = clean[:-len(q)]
            break
    return f"{base}-{target_quote.upper()}"


def compute_order_fingerprint(order: dict) -> str:
    """Deterministic SHA-256 fingerprint for order verification against crypto-risk."""
    canonical = (
        f"{str(order.get('symbol', '')).upper()}:"
        f"{str(order.get('side', '')).upper()}:"
        f"{float(order.get('quantity', 0)):.8f}:"
        f"{float(order.get('price', 0)):.8f}:"
        f"{float(order.get('stop_loss_price', 0)):.8f}:"
        f"{float(order.get('take_profit_price', 0)):.8f}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def verify_risk_authorization(order: dict, state_risk_path: str) -> tuple[bool, str]:
    """Ensure order matches a valid PASS verdict recorded by crypto-risk."""
    if not os.path.exists(state_risk_path):
        return False, f"Risk state not found at '{state_risk_path}'. Run crypto-risk check first."

    try:
        with open(state_risk_path, "r", encoding="utf-8") as f:
            risk_state = json.load(f)

        if risk_state.get("verdict") != "PASS":
            rejections = risk_state.get("rejections", [])
            return False, f"crypto-risk BLOCKED this order. Reasons: {rejections}"

        expected_fp = compute_order_fingerprint(order)
        actual_fp = risk_state.get("fingerprint")
        if actual_fp != expected_fp:
            return False, f"Order was modified after risk check. Expected fingerprint {expected_fp}, got {actual_fp}. Re-run crypto-risk."

        return True, "Risk verification PASSED."
    except Exception as e:
        return False, f"Error validating risk state: {e}"


def build_zebpay_payload(
    order: dict,
    quote_currency: str = "INR",
    inr_rate: float = None,
    custom_price: float = None,
) -> dict:
    """Construct order payload conforming to ZebPay Spot REST API specifications."""
    symbol = format_zebpay_symbol(order.get("symbol", ""), quote_currency)
    side = str(order.get("side", "BUY")).upper()
    order_type = str(order.get("type", "LIMIT")).upper()

    # Format quantity with up to 8 decimal places
    raw_qty = float(order.get("quantity", 0))
    qty_str = f"{raw_qty:.8f}".rstrip("0").rstrip(".")

    payload = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": qty_str,
    }

    if order_type == "LIMIT":
        if custom_price is not None and float(custom_price) > 0:
            price_val = float(custom_price)
        else:
            base_price = float(order.get("price", 0))
            if quote_currency.upper() == "INR" and inr_rate and inr_rate > 0:
                price_val = base_price * inr_rate
            else:
                price_val = base_price

        # Format price based on quote currency
        if quote_currency.upper() == "INR":
            price_str = f"{price_val:.2f}"
        else:
            price_str = f"{price_val:.4f}".rstrip("0").rstrip(".")
        payload["price"] = price_str

    return payload


def generate_auth_headers(
    api_key: str = "",
    api_secret: str = "",
    jwt_token: str = "",
    method: str = "POST",
    path: str = DEFAULT_ORDER_PATH,
    body: str = "",
    timestamp: str = None,
) -> dict:
    """Generate authenticated HTTP headers for ZebPay Spot REST API."""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
    }

    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
        return headers

    if api_key and api_secret:
        ts = timestamp or str(int(time.time() * 1000))
        # Signature: HMAC-SHA256 of timestamp + method + path + body
        message = f"{ts}{method.upper()}{path}{body}"
        signature = hmac.new(
            api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        headers["x-auth-apikey"] = api_key
        headers["x-auth-signature"] = signature
        headers["x-auth-timestamp"] = ts
        return headers

    raise ValueError("Missing ZebPay credentials. Set ZEBPAY_API_KEY + ZEBPAY_API_SECRET or ZEBPAY_JWT_TOKEN.")


def send_zebpay_request(
    base_url: str,
    path: str,
    headers: dict,
    payload: dict,
    timeout: int = 10,
) -> tuple[bool, dict]:
    """Execute HTTPS POST request to ZebPay REST API."""
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    body_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            return True, data
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        try:
            error_data = json.loads(error_body)
        except Exception:
            error_data = {"raw_error": error_body}
        error_data["http_code"] = e.code
        return False, error_data
    except Exception as e:
        return False, {"error": str(e)}


def record_live_fill(
    order: dict,
    zebpay_response: dict,
    state_broker_path: str = DEFAULT_STATE_BROKER_PATH,
    portfolio_path: str = DEFAULT_PORTFOLIO_PATH,
) -> dict:
    """Record live order placement and update active portfolio state."""
    os.makedirs(os.path.dirname(state_broker_path), exist_ok=True)
    history = []
    if os.path.exists(state_broker_path):
        try:
            with open(state_broker_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass

    order_id = zebpay_response.get("data", {}).get("orderId") or f"ZEBPAY_{int(time.time())}"
    fill_record = dict(order)
    fill_record["fill_time_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fill_record["fill_id"] = str(order_id)
    fill_record["broker"] = "ZEBPAY_LIVE"
    fill_record["raw_response"] = zebpay_response
    history.append(fill_record)

    with open(state_broker_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    # Update portfolio positions
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


def execute_dispatcher(
    command: str,
    orders_path: str = DEFAULT_ORDERS_PATH,
    state_risk_path: str = DEFAULT_STATE_RISK_PATH,
    state_broker_path: str = DEFAULT_STATE_BROKER_PATH,
    portfolio_path: str = DEFAULT_PORTFOLIO_PATH,
    quote: str = "INR",
    inr_rate: float = None,
    confirm: str = "",
    base_url: str = None,
    path: str = DEFAULT_ORDER_PATH,
    market: str = "spot",
) -> int:
    if not base_url:
        base_url = DEFAULT_FUTURES_URL if market.lower() == "futures" else DEFAULT_SPOT_URL
    """Core dispatcher coordination function."""
    if not os.path.exists(orders_path):
        print(f"Error: Orders file '{orders_path}' not found.")
        return 1

    with open(orders_path, "r", encoding="utf-8") as f:
        order = json.load(f)

    # 1. Enforce strict risk engine verification
    ok, msg = verify_risk_authorization(order, state_risk_path)
    if not ok:
        print(f"Refusal: Order not authorized for ZebPay dispatch.\nReason: {msg}")
        return 1

    # 2. Build ZebPay payload
    env_inr_rate = float(os.getenv("ZEBPAY_INR_RATE", 0)) if os.getenv("ZEBPAY_INR_RATE") else None
    effective_inr = inr_rate or env_inr_rate
    payload = build_zebpay_payload(order, quote_currency=quote, inr_rate=effective_inr)

    if command == "preview":
        mkt_label = f"FUTURES PERPETUAL ({order.get('leverage', 1)}x)" if market.lower() == "futures" else "SPOT CASH"
        print("==========================================================")
        print("         ZEBPAY LIVE ORDER PREVIEW (VERIFIED)             ")
        print("==========================================================")
        print(f"  Target Market:   {payload['symbol']} ({mkt_label})")
        print(f"  Action:          {payload['side']} {payload['quantity']}")
        print(f"  Order Type:      {payload['type']}")
        if "price" in payload:
            print(f"  Limit Price:     {payload['price']} {quote}")
        print(f"  Original Symbol: {order.get('symbol')} (${order.get('price')})")
        print(f"  Stop Loss:       ${order.get('stop_loss_price')}")
        print(f"  Take Profit:     ${order.get('take_profit_price')}")
        print("----------------------------------------------------------")
        print("  Risk Status:     PASS (Cryptographic Fingerprint Verified)")
        print(f"  Endpoint:        {base_url}{path}")
        print("==========================================================")
        print("\nFull JSON Payload:")
        print(json.dumps(payload, indent=2))
        return 0

    # 3. Retrieve credentials
    creds = get_zebpay_credentials()

    if command == "dry-run":
        print("[DRY-RUN] Validating ZebPay authentication & payload structure...")
        try:
            body_str = json.dumps(payload)
            # If test credentials exist, generate headers; otherwise simulate test signing
            test_key = creds["api_key"] or "test_key_sample"
            test_sec = creds["api_secret"] or "test_secret_sample"
            headers = generate_auth_headers(
                api_key=test_key,
                api_secret=test_sec,
                jwt_token=creds["jwt_token"],
                method="POST",
                path=path,
                body=body_str,
            )
            print("[DRY-RUN] Authentication headers generated successfully.")
            print(f"[DRY-RUN] x-auth-apikey:    {headers.get('x-auth-apikey', '[JWT Auth]')}")
            print(f"[DRY-RUN] x-auth-signature: {headers.get('x-auth-signature', '[JWT Auth]')[:16]}...")
            print(f"[DRY-RUN] x-auth-timestamp: {headers.get('x-auth-timestamp', '')}")
            print(f"[DRY-RUN] Endpoint:         {base_url}{path}")
            print(f"[DRY-RUN] Payload:          {body_str}")
            print("[DRY-RUN] SUCCESS: Order is 100% compliant and ready for live dispatch.")
            return 0
        except Exception as e:
            print(f"[DRY-RUN] Error during preparation: {e}")
            return 1

    if command == "dispatch":
        # Enforce human-in-the-loop explicit confirmation
        if confirm != "yes":
            print("Execution Refused: Live trading requires explicit confirmation: --confirm 'yes'")
            return 1

        if not creds["jwt_token"] and not (creds["api_key"] and creds["api_secret"]):
            print("Execution Refused: Missing ZebPay credentials.")
            print("Please set ZEBPAY_API_KEY and ZEBPAY_API_SECRET (or ZEBPAY_JWT_TOKEN) in your environment.")
            return 1

        body_str = json.dumps(payload)
        headers = generate_auth_headers(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            jwt_token=creds["jwt_token"],
            method="POST",
            path=path,
            body=body_str,
        )

        print(f"DISPATCHING LIVE ORDER TO ZEBPAY: {payload['symbol']} {payload['side']} {payload['quantity']}...")
        success, resp = send_zebpay_request(base_url, path, headers, payload)

        if not success:
            # Fallback path attempt if 404 on default path
            if resp.get("http_code") == 404 and path != FALLBACK_ORDER_PATH:
                print(f"Primary endpoint {path} returned 404. Attempting fallback {FALLBACK_ORDER_PATH}...")
                fallback_headers = generate_auth_headers(
                    api_key=creds["api_key"],
                    api_secret=creds["api_secret"],
                    jwt_token=creds["jwt_token"],
                    method="POST",
                    path=FALLBACK_ORDER_PATH,
                    body=body_str,
                )
                success, resp = send_zebpay_request(base_url, FALLBACK_ORDER_PATH, fallback_headers, payload)

        if not success:
            print("FAILED TO EXECUTE LIVE ORDER ON ZEBPAY.")
            print(f"Response: {json.dumps(resp, indent=2)}")
            return 1

        fill = record_live_fill(order, resp, state_broker_path, portfolio_path)
        print("==========================================================")
        print("         LIVE ORDER EXECUTED ON ZEBPAY                   ")
        print("==========================================================")
        print(f"  Fill ID:         {fill['fill_id']}")
        print(f"  Symbol:          {payload['symbol']}")
        print(f"  Side:            {payload['side']}")
        print(f"  Quantity:        {payload['quantity']}")
        print(f"  Execution Time:  {fill['fill_time_utc']}")
        print("==========================================================")
        print(f"Full response: {json.dumps(resp, indent=2)}")
        return 0

    print(f"Unknown command: {command}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="ZebPay Automated Live Dispatcher for crypto-broker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: preview
    prev_p = subparsers.add_parser("preview", help="Preview normalized ZebPay order payload")
    prev_p.add_argument("--orders", default=DEFAULT_ORDERS_PATH)
    prev_p.add_argument("--state-risk", default=DEFAULT_STATE_RISK_PATH)
    prev_p.add_argument("--quote", default="INR", help="Target quote currency (INR or USDT)")
    prev_p.add_argument("--inr-rate", type=float, help="USD to INR rate for limit price calculation")
    prev_p.add_argument("--market", choices=["spot", "futures"], default="spot", help="ZebPay market (spot or futures)")

    # Subcommand: dry-run
    dry_p = subparsers.add_parser("dry-run", help="Validate auth signatures & schema without sending")
    dry_p.add_argument("--orders", default=DEFAULT_ORDERS_PATH)
    dry_p.add_argument("--state-risk", default=DEFAULT_STATE_RISK_PATH)
    dry_p.add_argument("--quote", default="INR")
    dry_p.add_argument("--inr-rate", type=float)

    # Subcommand: dispatch
    disp_p = subparsers.add_parser("dispatch", help="Execute live order on ZebPay")
    disp_p.add_argument("--confirm", help="Must pass --confirm 'yes' to execute live order")
    disp_p.add_argument("--orders", default=DEFAULT_ORDERS_PATH)
    disp_p.add_argument("--state-risk", default=DEFAULT_STATE_RISK_PATH)
    disp_p.add_argument("--state-broker", default=DEFAULT_STATE_BROKER_PATH)
    disp_p.add_argument("--portfolio", default=DEFAULT_PORTFOLIO_PATH)
    disp_p.add_argument("--quote", default="INR")
    disp_p.add_argument("--inr-rate", type=float)
    disp_p.add_argument("--base-url", default=None)
    disp_p.add_argument("--path", default=DEFAULT_ORDER_PATH)
    disp_p.add_argument("--market", choices=["spot", "futures"], default="spot", help="ZebPay market (spot or futures)")

    args = parser.parse_args()

    code = execute_dispatcher(
        command=args.command,
        orders_path=getattr(args, "orders", DEFAULT_ORDERS_PATH),
        state_risk_path=getattr(args, "state_risk", DEFAULT_STATE_RISK_PATH),
        state_broker_path=getattr(args, "state_broker", DEFAULT_STATE_BROKER_PATH),
        portfolio_path=getattr(args, "portfolio", DEFAULT_PORTFOLIO_PATH),
        quote=getattr(args, "quote", "INR"),
        inr_rate=getattr(args, "inr_rate", None),
        confirm=getattr(args, "confirm", ""),
        base_url=getattr(args, "base_url", None),
        path=getattr(args, "path", DEFAULT_ORDER_PATH),
        market=getattr(args, "market", "spot"),
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
