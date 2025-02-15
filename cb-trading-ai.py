import jwt
import aiohttp
import asyncio
import secrets
import json
import time
import requests
from cryptography.hazmat.primitives import serialization
from collections import deque
import psycopg2 # type: ignore
from psycopg2.extras import Json # type: ignore
from decimal import Decimal
import numpy as np

DEBUG_MODE = False  # Set to True for debugging

# Load configuration from config.json
with open("config.json", "r") as f:
    config = json.load(f)

key_name = config["name"]
key_secret = config["privateKey"]
quote_currency = "USDC"
trade_percentage = config.get("trade_percentage", 10)  # % of available balance to trade
stop_loss_percentage = config.get("stop_loss_percentage", -10)  # Stop-loss threshold

request_host = "api.coinbase.com"

# Load coin-specific settings
coins_config = config.get("coins", {})
crypto_symbols = [symbol for symbol, settings in coins_config.items() if settings.get("enabled", False)]

# Database connection parameters
DB_HOST = config["database"]["host"]
DB_PORT = config["database"]["port"]
DB_NAME = config["database"]["name"]
DB_USER = config["database"]["user"]
DB_PASSWORD = config["database"]["password"]

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def query_ollama_verbose(prompt, model="mistral"):
    """Query the AI model for a detailed trading decision."""
    url = "http://192.168.1.22:11434/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}

    try:
        response = requests.post(url, json=payload)
        result = response.json()
        ai_response = result.get("response", "").strip()
        
        # Extract decision (first word) and keep explanation
        ai_parts = ai_response.split("\n", 1)
        decision = ai_parts[0].strip().upper()
        explanation = ai_parts[1].strip() if len(ai_parts) > 1 else "No explanation provided."
        
        return decision, explanation
    except Exception as e:
        print(f"🚨 AI Query Error: {e}")
        return "HOLD", "AI unavailable, defaulting to HOLD."

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
            return {"error": await response.text()}

async def log_trade(symbol, side, amount, price):
    """Log a trade in the trades table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO trades (symbol, side, amount, price)
        VALUES (%s, %s, %s, %s)
        """, (symbol, side, amount, price))
        conn.commit()
    except Exception as e:
        print(f"Error logging trade: {e}")
    finally:
        cursor.close()
        conn.close()

async def get_crypto_price(crypto_symbol):
    """Fetch cryptocurrency price from Coinbase asynchronously."""
    path = f"/api/v3/brokerage/products/{crypto_symbol}-{quote_currency}"
    data = await api_request("GET", path)
    
    return float(data["price"]) if "price" in data else None

def calculate_ema(prices, period, return_all=False):
    """Calculate the Exponential Moving Average (EMA) for a given period."""
    if len(prices) < period:
        return None if not return_all else []

    multiplier = 2 / (period + 1)
    ema_values = [sum(prices[:period]) / period]  # Start with SMA

    for price in prices[period:]:
        ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])

    return ema_values if return_all else ema_values[-1]

async def get_balances():
    """Fetch balances from Coinbase and return them as a dictionary."""
    path = "/api/v3/brokerage/accounts"
    data = await api_request("GET", path)  # Await the API request
    
    balances = {}
    if "accounts" in data:
        for account in data["accounts"]:
            currency = account["currency"]
            available_balance = float(account["available_balance"]["value"])
            balances[currency] = available_balance
    
    return balances

async def place_order(crypto_symbol, side, amount):
    """Place a buy/sell order for the specified cryptocurrency asynchronously."""
    path = "/api/v3/brokerage/orders"
    
    order_data = {
        "client_order_id": secrets.token_hex(16),
        "product_id": f"{crypto_symbol}-{quote_currency}",
        "side": side,
        "order_configuration": {
            "market_market_ioc": {}
        }
    }
    
    min_order_sizes = coins_config[crypto_symbol]["min_order_sizes"]
    
    if side == "BUY":
        # Round to 2 decimal places for quote currency (e.g., USDC)
        rounded_amount = round(amount, 2)
        if rounded_amount < min_order_sizes["buy"]:
            print(f"🚫 Buy order too small: ${rounded_amount:.2f} (minimum: ${min_order_sizes['buy']:.2f})")
            return False
        order_data["order_configuration"]["market_market_ioc"]["quote_size"] = str(rounded_amount)
    else:  # SELL
        # Round to the required precision for the base currency (e.g., ETH, BTC)
        rounded_amount = round(amount, 6)  # Adjust based on the coin's precision
        if rounded_amount < min_order_sizes["sell"]:
            print(f"🚫 Sell order too small: {rounded_amount:.6f} {crypto_symbol} (minimum: {min_order_sizes['sell']:.6f} {crypto_symbol})")
            return False
        order_data["order_configuration"]["market_market_ioc"]["base_size"] = str(rounded_amount)

    # Log the order details
    print(f"🛠️ Placing {side} order for {crypto_symbol}: Amount = {rounded_amount}, Price = {await get_crypto_price(crypto_symbol)}")

    response = await api_request("POST", path, order_data)

    if DEBUG_MODE:
        print(f"🔄 Raw Response: {response}")  # Only log raw response in debug mode

    # Handle the response
    if response.get("success", False):
        order_id = response["success_response"]["order_id"]
        print(f"✅ {side.upper()} Order Placed for {crypto_symbol}: Order ID = {order_id}")
        
        # Log the trade in the database
        current_price = await get_crypto_price(crypto_symbol)
        if current_price:
            log_trade(crypto_symbol, side, rounded_amount, current_price)

        return True
    else:
        print(f"❌ Order Failed for {crypto_symbol}: {response.get('error', 'Unknown error')}")
        return False

def calculate_macd(prices, symbol, short_window=12, long_window=26, signal_window=9):
    """Calculate MACD, Signal Line, and Histogram."""
    if len(prices) < long_window + signal_window:
        print(f"⚠️ Not enough data to calculate MACD for {symbol}. Required: {long_window + signal_window}, Available: {len(prices)}")
        return None, None, None

    # Compute EMA for the full dataset
    short_ema = calculate_ema(prices, short_window, return_all=True)
    long_ema = calculate_ema(prices, long_window, return_all=True)

    # Calculate MACD Line (difference between short and long EMA)
    macd_line_values = [s - l for s, l in zip(short_ema, long_ema)]

    # Calculate Signal Line (EMA of MACD Line)
    signal_line_values = calculate_ema(macd_line_values, signal_window, return_all=True)

    # Calculate MACD Histogram
    macd_histogram_values = [m - s for m, s in zip(macd_line_values[-len(signal_line_values):], signal_line_values)]

    # Log MACD values
    print(f"📊 {symbol} MACD Calculation - Short EMA: {short_ema[-1]:.2f}, Long EMA: {long_ema[-1]:.2f}, "
          f"MACD Line: {macd_line_values[-1]:.2f}, Signal Line: {signal_line_values[-1]:.2f}, "
          f"Histogram: {macd_histogram_values[-1]:.2f}")

    return macd_line_values[-1], signal_line_values[-1], macd_histogram_values[-1]

def calculate_rsi(prices, symbol, period=14):
    """Calculate the Relative Strength Index (RSI)."""
    if len(prices) < period + 1:
        print(f"⚠️ Not enough data to calculate RSI for {symbol}. Required: {period + 1}, Available: {len(prices)}")
        return None

    # Calculate gains and losses
    changes = np.diff(prices)
    gains = np.maximum(changes, 0)
    losses = np.maximum(-changes, 0)

    # Calculate average gains and losses
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # EMA smoothing for RSI
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    rs = avg_gain / avg_loss if avg_loss != 0 else float('inf')
    rsi = 100 - (100 / (1 + rs))

    print(f"📊 {symbol} RSI Calculation - Avg Gain: {avg_gain:.2f}, Avg Loss: {avg_loss:.2f}, RSI: {rsi:.2f}")
    return rsi

async def trading_bot():
    global crypto_data
    
    crypto_data = {symbol: {"price_history": deque(maxlen=200), "initial_price": None} for symbol in crypto_symbols}

    while True:
        await asyncio.sleep(30)

        # Fetch balances
        balances = await get_balances()
        
        # Fetch latest prices for all symbols
        price_tasks = [get_crypto_price(symbol) for symbol in crypto_symbols]
        prices = await asyncio.gather(*price_tasks)

        for symbol, current_price in zip(crypto_symbols, prices):
            if not current_price:
                continue
            
            price_history = crypto_data[symbol]["price_history"]
            price_history.append(current_price)

            if len(price_history) < 20:
                continue

            # Calculate MACD and RSI
            macd_line, signal_line, macd_histogram = calculate_macd(price_history, symbol)
            rsi = calculate_rsi(price_history, symbol)

            # Create AI Prompt
            ai_prompt = f"""
            Given the following market data:
            - {symbol} Current Price: {current_price}
            - MACD Line: {macd_line}
            - Signal Line: {signal_line}
            - MACD Histogram: {macd_histogram}
            - RSI: {rsi}
            - Available USDC: {balances.get(quote_currency, 0)}
            - Available {symbol}: {balances.get(symbol, 0)}

            Analyze the trend and explain whether I should BUY, SELL, or HOLD.
            Provide your decision as the first word (BUY, SELL, HOLD) followed by an explanation.
            """

            ai_decision, ai_explanation = query_ollama_verbose(ai_prompt)

            # Log AI response
            print(f"🤖 AI Decision for {symbol}: {ai_decision}")
            print(f"📢 AI Explanation: {ai_explanation}")

            # Execute AI-driven trade
            if ai_decision == "BUY" and balances.get(quote_currency, 0) > 0:
                buy_amount = (trade_percentage / 100) * balances[quote_currency] / current_price
                await place_order(symbol, "BUY", buy_amount)

            elif ai_decision == "SELL" and balances.get(symbol, 0) > 0:
                sell_amount = (trade_percentage / 100) * balances[symbol]
                await place_order(symbol, "SELL", sell_amount)

        print(f"✅ AI Trading Cycle Completed!")
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(trading_bot())
