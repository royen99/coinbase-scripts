import aiohttp
import asyncio
import jwt
import secrets
import json
import time
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

key_name = config["name"]
key_secret = config["privateKey"]
base_currency = "USDC"
quote_currency = "EUR"
product_id = f"{base_currency}-{quote_currency}"
trade_percentage = config.get("trade_percentage", 10)
buy_offset_percent = config.get("buy_offset_percent", -0.3)
sell_offset_percent = config.get("sell_offset_percent", 0.3)
cancel_hours = config.get("cancel_hours", 3)

request_host = "api.coinbase.com"
open_orders = {}

def build_jwt(uri):
    """Generate a JWT token for Coinbase API authentication."""
    private_key_bytes = key_secret.encode("utf-8")
    private_key = serialization.load_pem_private_key(private_key_bytes, password=None)

    jwt_payload = {
        "sub": key_name,
        "iss": "cdp",
        "nbf": int(time.time()),
        "exp": int(time.time()) + 120,
        "uri": uri,
    }

    jwt_token = jwt.encode(
        jwt_payload,
        private_key,
        algorithm="ES256",
        headers={"kid": key_name, "nonce": secrets.token_hex()},
    )

    return jwt_token if isinstance(jwt_token, str) else jwt_token.decode("utf-8")

async def api_request(method, path, body=None):
    """Send authenticated requests to Coinbase API asynchronously."""
    uri = f"{method} {request_host}{path}"
    jwt_token = build_jwt(uri)

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "CB-VERSION": "2024-02-05"
    }

    url = f"https://{request_host}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, headers=headers, json=body) as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": await response.text()}

async def get_order_book():
    path = f"/api/v3/brokerage/products/{product_id}/book?level=2"
    data = await api_request("GET", path)
    print("📦 Raw order book response:", json.dumps(data, indent=2))  # DEBUG
    try:
        best_bid = float(data["bids"][0]["price"]) if data.get("bids") else 0.0
        best_ask = float(data["asks"][0]["price"]) if data.get("asks") else 0.0
        print(f"📊 Best Bid: {best_bid}, Best Ask: {best_ask}")
        return best_bid, best_ask
    except Exception as e:
        print(f"🚨 Error reading order book: {e}")
        return 0.0, 0.0

async def get_balances():
    path = "/api/v3/brokerage/accounts"
    data = await api_request("GET", path)
    balances = {base_currency: 0.0, quote_currency: 0.0}
    for acct in data.get("accounts", []):
        c = acct["currency"]
        if c in balances:
            balances[c] = float(acct["available_balance"]["value"])
    print(f"💰 USDC: {balances[base_currency]:.2f}, EUR: {balances[quote_currency]:.2f}")
    return balances

async def place_limit_order(side, size, price):
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
    res = await api_request("POST", path, order_data)
    order_id = res.get("success_response", {}).get("order_id")
    if order_id:
        open_orders[order_id] = datetime.utcnow()
        print(f"✅ Order Placed: {order_id}")
    else:
        print(f"❌ Order Failed: {res.get('error_response', {}).get('message', res.get('error', 'Unknown'))}")

async def check_order_status(order_id):
    path = f"/api/v3/brokerage/orders/historical/{order_id}"
    data = await api_request("GET", path)
    return data.get("order", {}).get("order_status") == "FILLED"

async def cancel_order(order_id):
    path = f"/api/v3/brokerage/orders/{order_id}"
    uri = f"DELETE {request_host}{path}"
    jwt_token = build_jwt(uri)
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "CB-VERSION": "2024-02-05"
    }
    url = f"https://{request_host}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=headers) as res:
            print(f"❌ Cancelled Order: {order_id} -> {res.status}")

async def trading_bot():
    print(f"🤖 Starting USDC↔EUR limit trading on {product_id}")
    while True:
        best_bid, best_ask = await get_order_book()
        balances = await get_balances()
        now = datetime.utcnow()

        for order_id in list(open_orders.keys()):
            age = now - open_orders[order_id]
            if age > timedelta(hours=cancel_hours):
                await cancel_order(order_id)
                del open_orders[order_id]
            elif await check_order_status(order_id):
                print(f"✔️ Order Filled: {order_id}")
                del open_orders[order_id]

        if balances[quote_currency] > 5 and best_ask > 0:
            buy_price = best_ask * (1 + (buy_offset_percent / 100))
            amount = (trade_percentage / 100) * balances[quote_currency] / buy_price
            await place_limit_order("BUY", round(amount, 2), buy_price)

        if balances[base_currency] > 5 and best_bid > 0:
            sell_price = best_bid * (1 + (sell_offset_percent / 100))
            amount = (trade_percentage / 100) * balances[base_currency]
            await place_limit_order("SELL", round(amount, 2), sell_price)

        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(trading_bot())
