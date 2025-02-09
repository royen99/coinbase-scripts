import jwt
import requests
import time
import secrets
import json
from cryptography.hazmat.primitives import serialization
from collections import deque

# Load API credentials & trading settings from config.json
with open("config.json", "r") as f:
    config = json.load(f)

key_name = config["name"]
key_secret = config["privateKey"]
crypto_symbols = config.get("crypto_symbols", ["ETH", "XRP", "DOGE", "SOL"])  # List of cryptocurrencies to trade
quote_currency = "USDC"
buy_threshold = config.get("buy_percentage", -3)  # % drop to buy
sell_threshold = config.get("sell_percentage", 3)  # % rise to sell
trade_percentage = config.get("trade_percentage", 10)  # % of available balance to trade
stop_loss_percentage = config.get("stop_loss_percentage", -10)  # Stop-loss threshold
volatility_window = config.get("volatility_window", 10)  # Window for calculating volatility
trend_window = config.get("trend_window", 20)  # Window for calculating moving average

# Minimum order sizes (adjust based on Coinbase requirements for each cryptocurrency)
min_order_sizes = {
    "ETH": {"buy": 0.01, "sell": 0.0001},  # ETH minimums
    "XRP": {"buy": 0.01, "sell": 1},       # XRP minimums (example values, check Coinbase)
    "DOGE": {"buy": 0.01, "sell": 1},      # DOGE minimums (example values, check Coinbase)
    "SOL": {"buy": 0.01, "sell": 0.01},    # SOL minimums (example values, check Coinbase)
}

request_host = "api.coinbase.com"

# Initialize price_history with maxlen equal to the larger of volatility_window and trend_window
price_history_maxlen = max(volatility_window, trend_window)

# Load or initialize state
state_file = "state.json"
try:
    with open(state_file, "r") as f:
        crypto_data = json.load(f)
        # Convert price_history back to deque
        for symbol in crypto_symbols:
            if symbol in crypto_data:
                crypto_data[symbol]["price_history"] = deque(crypto_data[symbol]["price_history"], maxlen=price_history_maxlen)
except FileNotFoundError:
    crypto_data = {
        symbol: {
            "price_history": deque(maxlen=price_history_maxlen),
            "initial_price": None,
            "total_trades": 0,
            "total_profit": 0.0,
        }
        for symbol in crypto_symbols
    }

def save_state():
    """Save the current state to a file."""
    # Convert deque to list for JSON serialization
    state_to_save = {
        symbol: {
            **data,
            "price_history": list(data["price_history"]),
        }
        for symbol, data in crypto_data.items()
    }
    with open(state_file, "w") as f:
        json.dump(state_to_save, f, indent=2)

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

def api_request(method, path, body=None):
    """Send authenticated requests to Coinbase API."""
    uri = f"{method} {request_host}{path}"
    jwt_token = build_jwt(uri)

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "CB-VERSION": "2024-02-05"
    }

    url = f"https://{request_host}{path}"
    response = requests.request(method, url, headers=headers, json=body)

    return response.json() if response.status_code == 200 else {"error": response.text}

def get_crypto_price(crypto_symbol):
    """Fetch cryptocurrency price from Coinbase."""
    path = f"/api/v3/brokerage/products/{crypto_symbol}-{quote_currency}"
    data = api_request("GET", path)
    
    if "price" in data:
        return float(data["price"])
    
    print(f"Error fetching {crypto_symbol} price: {data.get('error', 'Unknown error')}")
    return None

def get_balances():
    """Fetch and display balances for all cryptocurrencies and USDC."""
    path = "/api/v3/brokerage/accounts"
    data = api_request("GET", path)
    
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

def place_order(crypto_symbol, side, amount):
    """Place a buy/sell order for the specified cryptocurrency."""
    path = "/api/v3/brokerage/orders"
    
    order_data = {
        "client_order_id": secrets.token_hex(16),
        "product_id": f"{crypto_symbol}-{quote_currency}",
        "side": side,
        "order_configuration": {
            "market_market_ioc": {}
        }
    }
    
    if side == "BUY":
        rounded_amount = round(amount, 2)  # USDC should have 2 decimal places
        if rounded_amount < min_order_sizes[crypto_symbol]["buy"]:
            print(f"🚫 Buy order too small: ${rounded_amount:.2f} (minimum: ${min_order_sizes[crypto_symbol]['buy']:.2f})")
            return False
        order_data["order_configuration"]["market_market_ioc"]["quote_size"] = str(rounded_amount)
    else:  # SELL
        rounded_amount = round(amount, 6)  # Cryptocurrency amount precision
        if rounded_amount < min_order_sizes[crypto_symbol]["sell"]:
            print(f"🚫 Sell order too small: {rounded_amount:.6f} {crypto_symbol} (minimum: {min_order_sizes[crypto_symbol]['sell']:.6f} {crypto_symbol})")
            return False
        order_data["order_configuration"]["market_market_ioc"]["base_size"] = str(rounded_amount)

    print(f"🛠️ Placing {side} order for {crypto_symbol}: {order_data}")  # Debugging: Print the full request payload

    response = api_request("POST", path, order_data)

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

def calculate_moving_average(price_history):
    """Calculate the moving average of prices."""
    if len(price_history) < trend_window:
        return None
    return sum(price_history) / len(price_history)

def calculate_macd(price_history, short_window=12, long_window=26, signal_window=9):
    """Calculate MACD and Signal Line."""
    if len(price_history) < long_window:
        return None, None  # Not enough data to calculate MACD
    
    # Short-term (12-period) EMA
    short_ema = sum(price_history[-short_window:]) / short_window
    # Long-term (26-period) EMA
    long_ema = sum(price_history[-long_window:]) / long_window
    
    macd_line = short_ema - long_ema
    # Signal Line (9-period EMA of MACD)
    signal_line = sum([macd_line] * signal_window) / signal_window  # Simple EMA for demonstration
    
    return macd_line, signal_line

def calculate_rsi(price_history, window=14):
    """Calculate RSI (Relative Strength Index)."""
    if len(price_history) < window:
        return None  # Not enough data to calculate RSI
    
    gains = []
    losses = []
    for i in range(1, window + 1):
        change = price_history[-i] - price_history[-(i + 1)]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window
    
    rs = avg_gain / avg_loss if avg_loss != 0 else float('inf')
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def trading_bot():
    """Monitors multiple cryptocurrencies and trades based on technical indicators."""
    global crypto_data

    # Initialize initial prices for all cryptocurrencies
    for symbol in crypto_symbols:
        if crypto_data[symbol]["initial_price"] is None:
            initial_price = get_crypto_price(symbol)
            if not initial_price:
                print(f"🚨 Failed to fetch initial {symbol} price. Skipping {symbol}.")
                continue
            crypto_data[symbol]["initial_price"] = initial_price
            print(f"🔍 Monitoring {symbol}... Initial Price: ${initial_price:.2f}")

    while True:
        time.sleep(30)  # Wait before checking prices again
        balances = get_balances()  # Fetch balances for all cryptocurrencies and USDC

        for symbol in crypto_symbols:
            current_price = get_crypto_price(symbol)
            if not current_price:
                continue

            # Update price history
            crypto_data[symbol]["price_history"].append(current_price)
            price_change = ((current_price - crypto_data[symbol]["initial_price"]) / crypto_data[symbol]["initial_price"]) * 100
            print(f"📈 {symbol} Price: ${current_price:.2f} ({price_change:.2f}%)")

            # Calculate MACD, Signal Line, and RSI
            macd_line, signal_line = calculate_macd(crypto_data[symbol]["price_history"])
            rsi = calculate_rsi(crypto_data[symbol]["price_history"])

            print(f"📊 {symbol} MACD: {macd_line:.2f} | Signal Line: {signal_line:.2f} | RSI: {rsi:.2f}")

            # Check for buy condition: MACD crosses above Signal Line and RSI is below 30
            if macd_line > signal_line and rsi < 30 and balances[quote_currency] > 0:
                buy_amount = (trade_percentage / 100) * balances[quote_currency] / current_price
                if buy_amount > 0:
                    print(f"💰 Buying {buy_amount:.4f} {symbol}!")
                    if place_order(symbol, "BUY", buy_amount):
                        crypto_data[symbol]["total_trades"] += 1
                        crypto_data[symbol]["initial_price"] = current_price  # Reset reference price

            # Check for sell condition: MACD crosses below Signal Line and RSI is above 70
            elif macd_line < signal_line and rsi > 70 and balances[symbol] > 0:
                sell_amount = (trade_percentage / 100) * balances[symbol]
                if sell_amount > 0:
                    print(f"💵 Selling {sell_amount:.4f} {symbol}!")
                    if place_order(symbol, "SELL", sell_amount):
                        crypto_data[symbol]["total_trades"] += 1
                        crypto_data[symbol]["total_profit"] += (current_price - crypto_data[symbol]["initial_price"]) * sell_amount
                        crypto_data[symbol]["initial_price"] = current_price  # Reset reference price

            # Log performance for each cryptocurrency
            print(f"📊 {symbol} Performance - Total Trades: {crypto_data[symbol]['total_trades']} | Total Profit: ${crypto_data[symbol]['total_profit']:.2f}")

        # Save state after each iteration
        save_state()

if __name__ == "__main__":
    trading_bot()
