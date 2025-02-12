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
import numpy as np

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
        print(f"💾 Saved {symbol} price history: ${price:.2f}")
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

            print(f"💾 Loaded state for {symbol}: Initial Price: ${initial_price:.2f}, Total Trades: {total_trades}, Total Profit: ${total_profit:.2f}, Price History: {price_history}")
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

def update_balances(balances):
    """Update the balances table in the database with the provided balances."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for currency, available_balance in balances.items():
            # Insert or update the balance in the database
            cursor.execute("""
            INSERT INTO balances (currency, available_balance)
            VALUES (%s, %s)
            ON CONFLICT (currency) DO UPDATE
            SET available_balance = EXCLUDED.available_balance
            """, (currency, available_balance))
        conn.commit()
    except Exception as e:
        print(f"Error updating balances: {e}")
    finally:
        cursor.close()
        conn.close()

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

        # Log the trade in the database
        current_price = await get_crypto_price(crypto_symbol)
        if current_price:
            log_trade(crypto_symbol, side, rounded_amount, current_price)

        return True
    else:
        print(f"❌ Order Failed for {crypto_symbol}: {response.get('error', 'Unknown error')}")
        return False

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

def calculate_volatility(price_history, volatility_window):
    """Calculate volatility as the standard deviation of price changes over a specific window."""
    if len(price_history) < volatility_window:
        return 0.0
    recent_prices = list(price_history)[-volatility_window:]
    price_changes = np.diff(recent_prices) / recent_prices[:-1]  # Percentage changes
    return np.std(price_changes)  # Standard deviation of returns

def calculate_moving_average(price_history, trend_window):
    """Calculate the simple moving average (SMA) of prices."""
    if len(price_history) < trend_window:
        return None
    return sum(price_history[-trend_window:]) / trend_window  # Use the last `trend_window` prices

def calculate_ema(prices, period, return_all=False):
    """Calculate the Exponential Moving Average (EMA) for a given period."""
    if len(prices) < period:
        return None if not return_all else []

    multiplier = 2 / (period + 1)
    ema_values = [sum(prices[:period]) / period]  # Start with SMA

    for price in prices[period:]:
        ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])

    return ema_values if return_all else ema_values[-1]

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

def calculate_long_term_ma(price_history, period=200):
    """Calculate the long-term moving average."""
    if len(price_history) < period:
        return None
    return sum(price_history[-period:]) / period

# Initialize crypto_data as a global variable
crypto_data = {}

# Global variable to track MACD confirmation
macd_confirmation = {symbol: {"buy": 0, "sell": 0} for symbol in crypto_symbols}

async def trading_bot():
    global crypto_data, macd_confirmation

    # Initialize initial prices for all cryptocurrencies
    for symbol in crypto_symbols:
        state = load_state(symbol)
        if state:
            crypto_data[symbol] = state
            print(f"🔍 Loaded state for {symbol}: {state}")
        else:
            initial_price = await get_crypto_price(symbol)
            if not initial_price:
                print(f"🚨 Failed to fetch initial {symbol} price. Skipping {symbol}.")
                continue
            crypto_data[symbol] = {
                "price_history": deque([initial_price], maxlen=price_history_maxlen),
                "initial_price": initial_price,
                "total_trades": 0,
                "total_profit": 0.0,
            }
            save_state(symbol, initial_price, 0, 0.0)
            print(f"🔍 Monitoring {symbol}... Initial Price: ${initial_price:.2f}, Price History: {crypto_data[symbol]['price_history']}")

    while True:
        await asyncio.sleep(30)  # Wait before checking prices again

        # Fetch balances
        balances = await get_balances()

        # Log balances
        print("💰 Available Balances:")
        for currency, balance in balances.items():
            print(f"  - {currency}: {balance}")

        # Update balances in the database
        update_balances(balances)

        # Fetch prices for all cryptocurrencies concurrently
        price_tasks = [get_crypto_price(symbol) for symbol in crypto_symbols]
        prices = await asyncio.gather(*price_tasks)

        for symbol, current_price in zip(crypto_symbols, prices):
            if not current_price:
                print(f"🚨 {symbol}: No price data. Skipping.")
                continue
            if symbol not in crypto_data:
                print(f"🚨 {symbol}: Not in crypto_data. Skipping.")
                continue
            if not crypto_data[symbol]["price_history"]:
                print(f"🚨 {symbol}: Empty price_history. Skipping.")
                continue
            if current_price == crypto_data[symbol]["price_history"][-1]:
                print(f"🚨 {symbol}: Price unchanged ({current_price:.2f} == {crypto_data[symbol]['price_history'][-1]:.2f}). Skipping.")
                continue

            # Save price history
            save_price_history(symbol, current_price)

            # Update price history in memory
            crypto_data[symbol]["price_history"].append(current_price)
            price_history = list(crypto_data[symbol]["price_history"])
            
            # Get coin-specific settings
            coin_settings = coins_config[symbol]
            buy_threshold = coin_settings["buy_percentage"]
            sell_threshold = coin_settings["sell_percentage"]
            volatility_window = coin_settings["volatility_window"]
            trend_window = coin_settings["trend_window"]
            macd_short_window = coin_settings["macd_short_window"]
            macd_long_window = coin_settings["macd_long_window"]
            macd_signal_window = coin_settings["macd_signal_window"]
            rsi_period = coin_settings["rsi_period"]

            # Ensure we have enough data for indicators
            if len(price_history) < max(macd_long_window + macd_signal_window, rsi_period + 1):
                print(f"⚠️ {symbol}: Not enough data for indicators. Required: {max(macd_long_window + macd_signal_window, rsi_period + 1)}, Available: {len(price_history)}")
                continue

            long_term_ma = calculate_long_term_ma(price_history, period=200)
            if long_term_ma is None:
                print(f"⚠️ {symbol}: Not enough data for long-term MA. Skipping.")
                continue

            price_change = ((current_price - crypto_data[symbol]["initial_price"]) / crypto_data[symbol]["initial_price"]) * 100
            print(f"📈 {symbol} Price: ${current_price:.2f} ({price_change:.2f}%)")

            # Calculate volatility and moving average
            volatility = calculate_volatility(price_history, volatility_window)
            volatility_factor = min(1.5, max(0.5, 1 + abs(volatility)))  # Cap extreme changes
            moving_avg = calculate_moving_average(price_history, trend_window)

            # Calculate indicators
            macd_line, signal_line, macd_histogram = calculate_macd(
                price_history, symbol, macd_short_window, macd_long_window, macd_signal_window
            )
            rsi = calculate_rsi(price_history, symbol)

            # Log indicator values
            print(f"📊 {symbol} Indicators - Volatility: {volatility:.2f}, Moving Avg: {moving_avg:.2f}, MACD: {macd_line:.2f}, Signal: {signal_line:.2f}, RSI: {rsi:.2f}")

            # Adjust thresholds based on volatility
            dynamic_buy_threshold = buy_threshold * volatility_factor
            dynamic_sell_threshold = sell_threshold * volatility_factor

            # Calculate expected buy/sell prices
            expected_buy_price = crypto_data[symbol]["initial_price"] * (1 + dynamic_buy_threshold / 100)
            expected_sell_price = crypto_data[symbol]["initial_price"] * (1 + dynamic_sell_threshold / 100)

            # Log expected prices
            print(f"📊 Expected Buy Price for {symbol}: ${expected_buy_price:.2f} (Dynamic Buy Threshold: {dynamic_buy_threshold:.2f}%)")
            print(f"📊 Expected Sell Price for {symbol}: ${expected_sell_price:.2f} (Dynamic Sell Threshold: {dynamic_sell_threshold:.2f}%)")

            # Check if the price is close to the moving average
            if moving_avg and abs(current_price - moving_avg) < (0.02 * moving_avg):  # Only trade if price is within 2% of the moving average
                # MACD Buy Signal: MACD line crosses above Signal line
                macd_buy_signal = macd_line is not None and signal_line is not None and macd_line > signal_line
                
                # RSI Buy Signal: RSI is below 30 (oversold)
                rsi_buy_signal = rsi is not None and rsi < 30
                
                # MACD Sell Signal: MACD line crosses below Signal line
                macd_sell_signal = macd_line is not None and signal_line is not None and macd_line < signal_line
                
                # RSI Sell Signal: RSI is above 70 (overbought)
                rsi_sell_signal = rsi is not None and rsi > 70

                # MACD Confirmation Rule with decay instead of full reset
                if macd_buy_signal:
                    macd_confirmation[symbol]["buy"] += 1
                    macd_confirmation[symbol]["sell"] = max(0, macd_confirmation[symbol]["sell"] - 1)
                elif macd_sell_signal:
                    macd_confirmation[symbol]["sell"] += 1
                    macd_confirmation[symbol]["buy"] = max(0, macd_confirmation[symbol]["buy"] - 1)
                else:
                    macd_confirmation[symbol]["buy"] = max(0, macd_confirmation[symbol]["buy"] - 1)
                    macd_confirmation[symbol]["sell"] = max(0, macd_confirmation[symbol]["sell"] - 1)

                # Log trading signals
                print(f"📊 {symbol} Trading Signals - MACD Buy: {macd_buy_signal}, RSI Buy: {rsi_buy_signal}, MACD Sell: {macd_sell_signal}, RSI Sell: {rsi_sell_signal}")
                print(f"📊 {symbol} MACD Confirmation - Buy: {macd_confirmation[symbol]['buy']}, Sell: {macd_confirmation[symbol]['sell']}")

                # Execute buy order if MACD buy signal is confirmed
                if (
                    (price_change <= dynamic_buy_threshold or  # Price threshold
                    (macd_buy_signal and macd_confirmation[symbol]["buy"] >= 3 and rsi < 30))  # MACD + RSI filter
                    and current_price > long_term_ma  # Trend filter
                    and balances[quote_currency] > 0  # Sufficient balance
                ):
                    buy_amount = (trade_percentage / 100) * balances[quote_currency] / current_price
                    if buy_amount > 0:
                        print(f"💰 Buying {buy_amount:.4f} {symbol}!")
                        if await place_order(symbol, "BUY", buy_amount):
                            crypto_data[symbol]["total_trades"] += 1
                            crypto_data[symbol]["initial_price"] = current_price  # Reset reference price
                    else:
                        print(f"🚫 Buy order too small: ${buy_amount:.2f} (minimum: ${coins_config[symbol]['min_order_sizes']['buy']:.2f})")

                # Execute sell order if MACD sell signal is confirmed
                elif (
                    (price_change >= dynamic_sell_threshold or  # Price threshold
                    (macd_sell_signal and macd_confirmation[symbol]["sell"] >= 3 and rsi > 70))  # MACD + RSI filter
                    and current_price < long_term_ma  # Trend filter
                    and balances[symbol] > 0  # Sufficient balance
                ):
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
