import jwt
import aiohttp
import asyncio
import secrets
import json
import time
from cryptography.hazmat.primitives import serialization
from collections import deque
import psycopg2 # type: ignore
from psycopg2.extras import Json # type: ignore
from decimal import Decimal

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

# Initialize price_history with maxlen equal to the larger of volatility_window and trend_window
price_history_maxlen = max(
    max(settings.get("volatility_window", 10) for settings in coins_config.values()),
    max(settings.get("trend_window", 20) for settings in coins_config.values())
)

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

def save_price_history(symbol, price):
    """Save price history to the PostgreSQL database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO price_history (symbol, price)
        VALUES (%s, %s)
        """, (symbol, price))
        conn.commit()
    except Exception as e:
        print(f"Error saving price history to database: {e}")
    finally:
        cursor.close()
        conn.close()

def save_state(symbol, initial_price, total_trades, total_profit):
    """Save the trading state to the PostgreSQL database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO trading_state (symbol, initial_price, total_trades, total_profit)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (symbol) DO UPDATE
        SET initial_price = EXCLUDED.initial_price,
            total_trades = EXCLUDED.total_trades,
            total_profit = EXCLUDED.total_profit
        """, (symbol, initial_price, total_trades, total_profit))
        conn.commit()
    except Exception as e:
        print(f"Error saving state to database: {e}")
    finally:
        cursor.close()
        conn.close()

def load_state(symbol):
    """Load the trading state from the PostgreSQL database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Load trading metrics from trading_state
        cursor.execute("""
        SELECT initial_price, total_trades, total_profit
        FROM trading_state
        WHERE symbol = %s
        """, (symbol,))
        row = cursor.fetchone()

        if row:
            # Convert decimal.Decimal to float if necessary
            initial_price = float(row[0]) if isinstance(row[0], Decimal) else row[0]
            total_trades = int(row[1])
            total_profit = float(row[2]) if isinstance(row[2], Decimal) else row[2]

            # Load price history from price_history table
            cursor.execute("""
            SELECT price
            FROM price_history
            WHERE symbol = %s
            ORDER BY timestamp DESC
            LIMIT %s
            """, (symbol, price_history_maxlen))
            price_history = [float(row[0]) for row in cursor.fetchall()]

            return {
                "price_history": deque(price_history, maxlen=price_history_maxlen),
                "initial_price": initial_price,
                "total_trades": total_trades,
                "total_profit": total_profit,
            }
        return None
    except Exception as e:
        print(f"Error loading state from database: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

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

async def get_crypto_price(crypto_symbol):
    """Fetch cryptocurrency price from Coinbase asynchronously."""
    path = f"/api/v3/brokerage/products/{crypto_symbol}-{quote_currency}"
    data = await api_request("GET", path)
    
    if "price" in data:
        return float(data["price"])
    
    print(f"Error fetching {crypto_symbol} price: {data.get('error', 'Unknown error')}")
    return None

async def get_balances():
    """Fetch and display balances for all cryptocurrencies and USDC asynchronously."""
    path = "/api/v3/brokerage/accounts"
    data = await api_request("GET", path)
    
    balances = {symbol: 0.0 for symbol in crypto_symbols}
    balances[quote_currency] = 0.0

    if "accounts" in data:
        for account in data["accounts"]:
            if account["currency"] in balances:
                balances[account["currency"]] = float(account["available_balance"]["value"])
    
    print(f"💰 Available Balances:")
    for symbol, balance in balances.items():
        print(f"  - {symbol}: {balance}")
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
        rounded_amount = round(amount, 2)  # USDC should have 2 decimal places
        if rounded_amount < min_order_sizes["buy"]:
            print(f"🚫 Buy order too small: ${rounded_amount:.2f} (minimum: ${min_order_sizes['buy']:.2f})")
            return False
        order_data["order_configuration"]["market_market_ioc"]["quote_size"] = str(rounded_amount)
    else:  # SELL
        rounded_amount = round(amount, 6)  # Cryptocurrency amount precision
        if rounded_amount < min_order_sizes["sell"]:
            print(f"🚫 Sell order too small: {rounded_amount:.6f} {crypto_symbol} (minimum: {min_order_sizes['sell']:.6f} {crypto_symbol})")
            return False
        order_data["order_configuration"]["market_market_ioc"]["base_size"] = str(rounded_amount)

    print(f"🛠️ Placing {side} order for {crypto_symbol}: {order_data}")  # Debugging: Print the full request payload

    response = await api_request("POST", path, order_data)

    print(f"🔄 Raw Response: {response}")  # Debugging: Print the full response

    # Handle the response based on the new structure
    if response.get("success", False):
        order_id = response["success_response"]["order_id"]
        print(f"✅ {side.upper()} Order Placed for {crypto_symbol}: {order_id}")
        return True
    else:
        print(f"❌ Order Failed for {crypto_symbol}: {response.get('error', 'Unknown error')}")
        return False

def calculate_volatility(price_history):
    """Calculate volatility as the standard deviation of price changes."""
    if len(price_history) < 2:
        return 0.0
    price_changes = [(price_history[i] - price_history[i - 1]) / price_history[i - 1] for i in range(1, len(price_history))]
    return sum(price_changes) / len(price_changes)  # Average price change

def calculate_moving_average(price_history, trend_window):
    """Calculate the moving average of prices."""
    if len(price_history) < trend_window:
        return None
    return sum(price_history) / len(price_history)

def calculate_ema(prices, period):
    """Calculate the Exponential Moving Average (EMA) for a given period."""
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period  # Start with SMA
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_macd(prices, symbol, short_window=12, long_window=26, signal_window=9):
    """Calculate MACD and Signal Line."""
    if len(prices) < long_window + signal_window:
        print(f"⚠️ Not enough data to calculate MACD for {symbol}. Required: {long_window + signal_window}, Available: {len(prices)}")
        return None, None, None

    # Calculate short-term and long-term EMAs
    short_ema = calculate_ema(prices, short_window)
    long_ema = calculate_ema(prices, long_window)

    # Calculate MACD line
    macd_line = short_ema - long_ema

    # Calculate Signal line (EMA of MACD line)
    signal_line = calculate_ema(prices[-signal_window:], signal_window)

    # Calculate MACD Histogram
    macd_histogram = macd_line - signal_line

    print(f"📊 {symbol} MACD Calculation - Short EMA: {short_ema:.2f}, Long EMA: {long_ema:.2f}, MACD Line: {macd_line:.2f}, Signal Line: {signal_line:.2f}, Histogram: {macd_histogram:.2f}")
    return macd_line, signal_line, macd_histogram

def calculate_rsi(prices, symbol, period=14):
    """Calculate the Relative Strength Index (RSI)."""
    if len(prices) < period:
        print(f"⚠️ Not enough data to calculate RSI for {symbol}. Required: {period}, Available: {len(prices)}")
        return None

    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        rsi = 100  # Avoid division by zero
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    print(f"📊 {symbol} RSI Calculation - Avg Gain: {avg_gain:.2f}, Avg Loss: {avg_loss:.2f}, RSI: {rsi:.2f}")
    return rsi

# Initialize crypto_data as a global variable
crypto_data = {}

async def trading_bot():
    """Monitors multiple cryptocurrencies and trades based on technical indicators."""
    global crypto_data

    # Initialize initial prices for all cryptocurrencies
    for symbol in crypto_symbols:
        state = load_state(symbol)
        if state:
            crypto_data[symbol] = state
        else:
            initial_price = await get_crypto_price(symbol)
            if not initial_price:
                print(f"🚨 Failed to fetch initial {symbol} price. Skipping {symbol}.")
                continue
            crypto_data[symbol] = {
                "price_history": deque(maxlen=price_history_maxlen),
                "initial_price": initial_price,
                "total_trades": 0,
                "total_profit": 0.0,
            }
            save_state(symbol, initial_price, 0, 0.0)
            print(f"🔍 Monitoring {symbol}... Initial Price: ${initial_price:.2f}")

    while True:
        await asyncio.sleep(30)  # Wait before checking prices again
        balances = await get_balances()  # Fetch balances for all cryptocurrencies and USDC

        # Fetch prices for all cryptocurrencies concurrently
        price_tasks = [get_crypto_price(symbol) for symbol in crypto_symbols]
        prices = await asyncio.gather(*price_tasks)

        for symbol, current_price in zip(crypto_symbols, prices):
            if not current_price:
                continue

            # Save price history
            save_price_history(symbol, current_price)

            # Update price history in memory
            crypto_data[symbol]["price_history"].append(current_price)
            price_history = list(crypto_data[symbol]["price_history"])
            price_change = ((current_price - crypto_data[symbol]["initial_price"]) / crypto_data[symbol]["initial_price"]) * 100
            print(f"📈 {symbol} Price: ${current_price:.2f} ({price_change:.2f}%)")

            # Get coin-specific settings
            coin_settings = coins_config[symbol]
            buy_threshold = coin_settings["buy_percentage"]
            sell_threshold = coin_settings["sell_percentage"]
            volatility_window = coin_settings["volatility_window"]
            trend_window = coin_settings["trend_window"]

            # Calculate volatility and moving average
            volatility = calculate_volatility(price_history)
            moving_avg = calculate_moving_average(price_history, trend_window)

            # Calculate MACD and RSI
            macd_line, signal_line, macd_histogram = calculate_macd(price_history, symbol)
            rsi = calculate_rsi(price_history, symbol)

            # Log MACD and RSI values (if available)
            if macd_line is not None and signal_line is not None and rsi is not None:
                print(f"📊 {symbol} MACD: {macd_line:.2f}, Signal: {signal_line:.2f}, Histogram: {macd_histogram:.2f}")
                print(f"📊 {symbol} RSI: {rsi:.2f}")

            # Adjust thresholds based on volatility
            dynamic_buy_threshold = buy_threshold * (1 + abs(volatility))
            dynamic_sell_threshold = sell_threshold * (1 + abs(volatility))

            # Calculate expected buy/sell prices
            expected_buy_price = crypto_data[symbol]["initial_price"] * (1 + dynamic_buy_threshold / 100)
            expected_sell_price = crypto_data[symbol]["initial_price"] * (1 + dynamic_sell_threshold / 100)

            # Log expected prices
            print(f"📊 Expected Buy Price for {symbol}: ${expected_buy_price:.2f}")
            print(f"📊 Expected Sell Price for {symbol}: ${expected_sell_price:.2f}")

            # Check if the price is close to the moving average
            if moving_avg and abs(current_price - moving_avg) < (0.02 * moving_avg):  # Only trade if price is within 2% of the moving average
                # MACD Buy Signal: MACD line crosses above Signal line
                macd_buy_signal = macd_line and signal_line and macd_line > signal_line

                # RSI Buy Signal: RSI is below 30 (oversold)
                rsi_buy_signal = rsi and rsi < 30

                # MACD Sell Signal: MACD line crosses below Signal line
                macd_sell_signal = macd_line and signal_line and macd_line < signal_line

                # RSI Sell Signal: RSI is above 70 (overbought)
                rsi_sell_signal = rsi and rsi > 70

                if (price_change <= dynamic_buy_threshold or macd_buy_signal or rsi_buy_signal) and balances[quote_currency] > 0:
                    buy_amount = (trade_percentage / 100) * balances[quote_currency] / current_price
                    if buy_amount > 0:
                        print(f"💰 Buying {buy_amount:.4f} {symbol}!")
                        if await place_order(symbol, "BUY", buy_amount):
                            crypto_data[symbol]["total_trades"] += 1
                            crypto_data[symbol]["initial_price"] = current_price  # Reset reference price

                elif (price_change >= dynamic_sell_threshold or macd_sell_signal or rsi_sell_signal) and balances[symbol] > 0:
                    sell_amount = (trade_percentage / 100) * balances[symbol]
                    if sell_amount > 0:
                        print(f"💵 Selling {sell_amount:.4f} {symbol}!")
                        if await place_order(symbol, "SELL", sell_amount):
                            crypto_data[symbol]["total_trades"] += 1
                            crypto_data[symbol]["total_profit"] += (current_price - crypto_data[symbol]["initial_price"]) * sell_amount
                            crypto_data[symbol]["initial_price"] = current_price  # Reset reference price

            # Log performance for each cryptocurrency
            print(f"📊 {symbol} Performance - Total Trades: {crypto_data[symbol]['total_trades']} | Total Profit: ${crypto_data[symbol]['total_profit']:.2f}")

            # Save state after each coin's update
            save_state(symbol, crypto_data[symbol]["initial_price"], crypto_data[symbol]["total_trades"], crypto_data[symbol]["total_profit"])

if __name__ == "__main__":
    asyncio.run(trading_bot())
