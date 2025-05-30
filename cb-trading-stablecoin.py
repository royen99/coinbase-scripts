import aiohttp
import asyncio
import jwt
import secrets
import json
import time
import psycopg2
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

# Database connection parameters
DB_HOST = config["database"]["host"]
DB_PORT = config["database"]["port"]
DB_NAME = config["database"]["name"]
DB_USER = config["database"]["user"]
DB_PASSWORD = config["database"]["password"]

def get_db_connection():
    """Connect to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

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
    path = "/api/v3/brokerage/best_bid_ask"
    data = await api_request("GET", path)

    try:
        for book in data.get("pricebooks", []):
            if book.get("product_id") == product_id:
                best_bid = float(book["bids"][0]["price"]) if book.get("bids") else 0.0
                best_ask = float(book["asks"][0]["price"]) if book.get("asks") else 0.0
                print(f"📊 Best Bid: {best_bid}, Best Ask: {best_ask}")
                return best_bid, best_ask
        print("🚫 USDC-EUR not found in best_bid_ask response.")
        return 0.0, 0.0
    except Exception as e:
        print(f"🚨 Parsing error: {e} — Raw: {data}")
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

def save_initial_price(symbol, price):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO trading_state (symbol, initial_price, total_trades, total_profit)
            VALUES (%s, %s, 0, 0)
            ON CONFLICT (symbol) DO UPDATE
            SET initial_price = EXCLUDED.initial_price
        """, (symbol, price))
        conn.commit()
    except Exception as e:
        print(f"❌ Error saving initial price: {e}")
    finally:
        cursor.close()
        conn.close()

def load_initial_price(symbol):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT initial_price FROM trading_state WHERE symbol = %s", (symbol,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"❌ Error loading initial price: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def save_price_history(symbol, price):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO price_history (symbol, price)
        VALUES (%s, %s)
        """, (symbol, price))
        conn.commit()
    except Exception as e:
        print(f"💾 Error saving price: {e}")
    finally:
        cursor.close()
        conn.close()

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
    symbol = product_id
    initial_price = load_initial_price(symbol)

    if not initial_price:
        _, initial_ask = await get_order_book()
        initial_price = initial_ask
        save_initial_price(symbol, initial_price)
        print(f"📌 Saved new initial price: {initial_price}")
    else:
        print(f"📌 Loaded initial price from DB: {initial_price}")

    while True:
        best_bid, best_ask = await get_order_book()
        balances = await get_balances()

        save_price_history("USDC-EUR", best_bid)

        # 💸 Calculate candidate prices based on offsets
        buy_price = round(initial_price * (1 + (buy_offset_percent / 100)), 4)
        sell_price = round(initial_price * (1 + (sell_offset_percent / 100)), 4)

        print(f"🔍 Buy Target: {buy_price} (offset {buy_offset_percent}%)")
        print(f"🔍 Sell Target: {sell_price} (offset {sell_offset_percent}%)")

        # Add preview logic
        if balances[quote_currency] > 5:
            amount = round((trade_percentage / 100) * balances[quote_currency] / buy_price, 2)
            print(f"✅ Would BUY ~{amount} USDC at {buy_price} (EUR: {balances[quote_currency]:.2f})")
        else:
            print("⛔ Not enough EUR to buy.")

        if balances[base_currency] > 5:
            amount = round((trade_percentage / 100) * balances[base_currency], 2)
            print(f"✅ Would SELL ~{amount} USDC at {sell_price} (USDC: {balances[base_currency]:.2f})")
        else:
            print("⛔ Not enough USDC to sell.")

        now = datetime.utcnow()

        for order_id in list(open_orders.keys()):
            age = now - open_orders[order_id]
            if age > timedelta(hours=cancel_hours):
                await cancel_order(order_id)
                del open_orders[order_id]
            elif await check_order_status(order_id):
                print(f"✔️ Order Filled: {order_id}")
                del open_orders[order_id]

            # BUY = spend EUR to get USDC
            if balances[quote_currency] > 5 and best_ask > 0:
                amount = (trade_percentage / 100) * balances[quote_currency] / buy_price
                await place_limit_order("BUY", round(amount, 2), buy_price)

            # SELL = sell USDC to get EUR
            if balances[base_currency] > 5 and best_bid > 0:
                amount = (trade_percentage / 100) * balances[base_currency]
                await place_limit_order("SELL", round(amount, 2), sell_price)

        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(trading_bot())
