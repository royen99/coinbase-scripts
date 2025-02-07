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
base_currency = "ETH"
quote_currency = "USDC"
buy_threshold = config.get("buy_percentage", -3)  # % drop to buy
sell_threshold = config.get("sell_percentage", 3)  # % rise to sell
trade_percentage = config.get("trade_percentage", 10)  # % of available balance to trade
stop_loss_percentage = config.get("stop_loss_percentage", -10)  # Stop-loss threshold
volatility_window = config.get("volatility_window", 10)  # Window for calculating volatility
trend_window = config.get("trend_window", 20)  # Window for calculating moving average

# Minimum order sizes
min_buy_usdc = 0.01  # Minimum USDC amount for buy orders
min_sell_eth = 0.0001  # Minimum ETH amount for sell orders

request_host = "api.coinbase.com"

# Track price history for volatility and trend analysis
price_history = deque(maxlen=volatility_window)
initial_price = None
total_trades = 0
total_profit = 0.0

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

def get_eth_price():
    """Fetch ETH-USDC price from Coinbase."""
    path = f"/api/v3/brokerage/products/{base_currency}-{quote_currency}"
    data = api_request("GET", path)
    
    if "price" in data:
        return float(data["price"])
    
    print(f"Error fetching ETH price: {data.get('error', 'Unknown error')}")
    return None

def get_balances():
    """Fetch and display balances for ETH and USDC."""
    path = "/api/v3/brokerage/accounts"
    data = api_request("GET", path)
    
    balances = {"ETH": 0.0, "USDC": 0.0}

    if "accounts" in data:
        for account in data["accounts"]:
            if account["currency"] in balances:
                balances[account["currency"]] = float(account["available_balance"]["value"])
    
    print(f"💰 Available Balance - ETH: {balances['ETH']} | USDC: {balances['USDC']}")
    return balances

def place_order(side, amount):
    """Place a buy/sell order for ETH-USDC."""
    path = "/api/v3/brokerage/orders"
    
    order_data = {
        "client_order_id": secrets.token_hex(16),
        "product_id": f"{base_currency}-{quote_currency}",
        "side": side,
        "order_configuration": {
            "market_market_ioc": {}
        }
    }
    
    if side == "BUY":
        rounded_amount = round(amount, 2)  # USDC should have 2 decimal places
        if rounded_amount < min_buy_usdc:
            print(f"🚫 Buy order too small: ${rounded_amount:.2f} (minimum: ${min_buy_usdc:.2f})")
            return False
        order_data["order_configuration"]["market_market_ioc"]["quote_size"] = str(rounded_amount)
    else:  # SELL
        rounded_amount = round(amount, 6)  # ETH should have 6 decimal places
        if rounded_amount < min_sell_eth:
            print(f"🚫 Sell order too small: {rounded_amount:.6f} ETH (minimum: {min_sell_eth:.6f} ETH)")
            return False
        order_data["order_configuration"]["market_market_ioc"]["base_size"] = str(rounded_amount)

    print(f"🛠️ Placing {side} order: {order_data}")  # Debugging: Print the full request payload

    response = api_request("POST", path, order_data)

    print(f"🔄 Raw Response: {response}")  # Debugging: Print the full response

    # Handle the response based on the new structure
    if response.get("success", False):
        order_id = response["success_response"]["order_id"]
        print(f"✅ {side.upper()} Order Placed: {order_id}")
        return True
    else:
        print(f"❌ Order Failed: {response.get('error', 'Unknown error')}")
        return False

def calculate_volatility():
    """Calculate volatility as the standard deviation of price changes."""
    if len(price_history) < 2:
        return 0.0
    price_changes = [(price_history[i] - price_history[i - 1]) / price_history[i - 1] for i in range(1, len(price_history))]
    return sum(price_changes) / len(price_changes)  # Average price change

def calculate_moving_average():
    """Calculate the moving average of prices."""
    if len(price_history) < trend_window:
        return None
    return sum(price_history) / len(price_history)

def trading_bot():
    """Monitors ETH price and trades based on percentage changes, using % of available balance."""
    global initial_price, total_trades, total_profit

    initial_price = get_eth_price()
    if not initial_price:
        print("🚨 Failed to fetch initial ETH price. Exiting.")
        return

    print(f"🔍 Monitoring ETH... Initial Price: ${initial_price:.2f}")

    while True:
        time.sleep(30)  # Wait before checking price again
        current_price = get_eth_price()
        if not current_price:
            continue

        price_history.append(current_price)
        price_change = ((current_price - initial_price) / initial_price) * 100
        print(f"📈 ETH Price: ${current_price:.2f} ({price_change:.2f}%)")

        # Calculate volatility and moving average
        volatility = calculate_volatility()
        moving_avg = calculate_moving_average()

        # Adjust thresholds based on volatility
        dynamic_buy_threshold = buy_threshold * (1 + abs(volatility))
        dynamic_sell_threshold = sell_threshold * (1 + abs(volatility))

        # Fetch balances
        balances = get_balances()

        # Check for stop-loss condition
        if price_change <= stop_loss_percentage and balances["ETH"] > 0:
            sell_amount = balances["ETH"]
            print(f"🚨 Stop-loss triggered! Selling {sell_amount:.4f} ETH!")
            if place_order("SELL", sell_amount):
                total_trades += 1
                total_profit += (current_price - initial_price) * sell_amount
                initial_price = current_price  # Reset reference price
            continue

        # Check for buy/sell conditions with trend filter
        if moving_avg and abs(current_price - moving_avg) < (0.02 * moving_avg):  # Only trade if price is close to moving average
            if price_change <= dynamic_buy_threshold and balances["USDC"] > 0:
                buy_amount = (trade_percentage / 100) * balances["USDC"] / current_price
                if buy_amount > 0:
                    print(f"💰 Buying {buy_amount:.4f} ETH!")
                    if place_order("BUY", buy_amount):
                        total_trades += 1
                        initial_price = current_price  # Reset reference price

            elif price_change >= dynamic_sell_threshold and balances["ETH"] > 0:
                sell_amount = (trade_percentage / 100) * balances["ETH"]
                if sell_amount > 0:
                    print(f"💵 Selling {sell_amount:.4f} ETH!")
                    if place_order("SELL", sell_amount):
                        total_trades += 1
                        total_profit += (current_price - initial_price) * sell_amount
                        initial_price = current_price  # Reset reference price

        # Log performance
        print(f"📊 Total Trades: {total_trades} | Total Profit: ${total_profit:.2f}")

if __name__ == "__main__":
    trading_bot()
