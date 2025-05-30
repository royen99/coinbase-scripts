import jwt
import requests
import time
import secrets
import json
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization

with open("config.json", "r") as f:
    config = json.load(f)

key_name = config["name"]
key_secret = config["privateKey"]
base_currency = "USDC"
quote_currency = "EUR"
trade_percentage = config.get("trade_percentage", 10)
buy_offset_percent = config.get("buy_offset_percent", -0.3)  # e.g. -0.3% below ask
sell_offset_percent = config.get("sell_offset_percent", 0.3)  # e.g. 0.3% above bid
cancel_hours = config.get("cancel_hours", 3)

request_host = "api.coinbase.com"
product_id = f"{base_currency}-{quote_currency}"

open_orders = {}

def build_jwt(uri):
    private_key = serialization.load_pem_private_key(key_secret.encode(), password=None)
    payload = {
        "sub": key_name,
        "iss": "cdp",
        "nbf": int(time.time()),
        "exp": int(time.time()) + 120,
        "uri": uri,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": key_name, "nonce": secrets.token_hex()})

def api_request(method, path, body=None):
    uri = f"{method} {request_host}{path}"
    token = build_jwt(uri)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "CB-VERSION": "2024-02-05"
    }
    url = f"https://{request_host}{path}"
    res = requests.request(method, url, headers=headers, json=body)
    return res.json() if res.status_code == 200 else {"error": res.text}

def get_order_book():
    path = f"/api/v3/brokerage/products/{product_id}/book?level=2"
    data = api_request("GET", path)
    try:
        best_bid = float(data["bids"][0]["price"]) if data.get("bids") else 0.0
        best_ask = float(data["asks"][0]["price"]) if data.get("asks") else 0.0
        print(f"📊 Best Bid: {best_bid}, Best Ask: {best_ask}")
        return best_bid, best_ask
    except Exception as e:
        print(f"🚨 Error reading order book: {e}")
        return 0.0, 0.0

def get_balances():
    path = "/api/v3/brokerage/accounts"
    data = api_request("GET", path)
    balances = {base_currency: 0.0, quote_currency: 0.0}
    for acct in data.get("accounts", []):
        c = acct["currency"]
        if c in balances:
            balances[c] = float(acct["available_balance"]["value"])
    print(f"💰 USDC: {balances[base_currency]:.2f}, EUR: {balances[quote_currency]:.2f}")
    return balances

def place_limit_order(side, size, price):
    path = "/api/v3/brokerage/orders"
    order_data = {
        "client_order_id": secrets.token_hex(16),
        "product_id": product_id,
        "side": side,
        "order_configuration": {
            "limit_limit_gtc": {
                "base_size": str(size),
                "limit_price": str(round(price, 4)),
                "post_only": True
            }
        }
    }
    print(f"🛒 Placing {side} order at {round(price, 4)} for {size}")
    res = api_request("POST", path, order_data)
    order_id = res.get("success_response", {}).get("order_id")
    if order_id:
        open_orders[order_id] = datetime.utcnow()
        print(f"✅ Order Placed: {order_id}")
    else:
        print(f"❌ Order Failed: {res.get('error_response', {}).get('message')}")

def check_order_status(order_id):
    path = f"/api/v3/brokerage/orders/historical/{order_id}"
    data = api_request("GET", path)
    return data.get("order", {}).get("order_status") == "FILLED"

def cancel_order(order_id):
    path = f"/api/v3/brokerage/orders/{order_id}"
    res = requests.delete(f"https://{request_host}{path}", headers={
        "Authorization": f"Bearer {build_jwt(f'DELETE {request_host}{path}')}",
        "Content-Type": "application/json",
        "CB-VERSION": "2024-02-05"
    })
    print(f"❌ Cancelled Order: {order_id} -> {res.status_code}")

def trading_bot():
    print(f"🤖 Starting USDC↔EUR limit trading on {product_id}")
    while True:
        best_bid, best_ask = get_order_book()
        balances = get_balances()

        now = datetime.utcnow()
        for order_id in list(open_orders.keys()):
            age = now - open_orders[order_id]
            if age > timedelta(hours=cancel_hours):
                cancel_order(order_id)
                del open_orders[order_id]
            elif check_order_status(order_id):
                print(f"✔️ Order Filled: {order_id}")
                del open_orders[order_id]

        # BUY USDC → EUR (quote → base)
        if balances[quote_currency] > 5:
            buy_price = best_ask * (1 + (buy_offset_percent / 100))
            amount = (trade_percentage / 100) * balances[quote_currency] / buy_price
            place_limit_order("BUY", round(amount, 2), buy_price)

        # SELL EUR → USDC (base → quote)
        if balances[base_currency] > 5:
            sell_price = best_bid * (1 + (sell_offset_percent / 100))
            amount = (trade_percentage / 100) * balances[base_currency]
            place_limit_order("SELL", round(amount, 2), sell_price)

        time.sleep(60)

if __name__ == "__main__":
    trading_bot()
