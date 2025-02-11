# coinbase-scripts
Coinbase crypto trading API scripts.

Note that everything is still under development! Use these scripts as your own risk.

✅ Directly makes the API request (using JWT's).\
✅ Handles API responses & errors, printing available balances or errors properly.\
✅ Uses config.json for credentials, keeping them separate from the script.

## How It Works

All scripts need at least a `config.json` file that has your Coinbase API credentials and a 

### Config Example (config.json)
```json
{
    "name": "organizations/{org_id}/apiKeys/{key_id}",
    "privateKey": "-----BEGIN EC PRIVATE KEY-----\nYOUR PRIVATE KEY\n-----END EC PRIVATE KEY-----\n"
}
```

See the `config.json.template` file for the full example (some scripts utilize additional settings).

**Ensure the `config.json` is securely stored**

### cb-trading-db.py
The `cb-trading-db.py` script is the main project (see below for for scripts with less functionality).

✅ Uses a PostgreSQL database backend for saving and loading price history and trading state.\
✅ Asynchronous API requests, improving performance and responsiveness.\
✅ Concurrent Price Fetching. Fetches prices for all cryptocurrencies simultaneously.\
✅ Trades multiple cryptocurrencies with configurable settings.\
✅ Moving Average Convergence Divergence (MACD) to identify trend direction and momentum.\
✅ Relative Strength Index (RSI) to identify overbought and oversold conditions.\
✅ Integrated MACD and RSI signals into the trading strategy.

Additional settings (inside the `config.json`) are needed holding your database info and which coins you want to enable/disable.\
You can adjust `trade_percentage` to control how much of your balance gets traded. 😘💸\
**Fine-Tune Parameters**: Adjust the `volatility_window`, `trend_window`, and `stop_loss_percentage` to suit your risk tolerance and market conditions. 📊

```json
{
  "name": "organizations/{org_id}/apiKeys/{key_id}",
  "privateKey": "-----BEGIN EC PRIVATE KEY-----\nYOUR PRIVATE KEY\n-----END EC PRIVATE KEY-----\n",
  "trade_percentage": 10,
  "stop_loss_percentage": -10,
  "database": {
    "host": "your-database-host",
    "port": "your-database-port",
    "name": "your-database-name",
    "user": "your-database-user",
    "password": "your-database-password"
  },
  "coins": {
    "ETH": {
      "enabled": true,
      "buy_percentage": -3,
      "sell_percentage": 3,
      "volatility_window": 10,
      "trend_window": 26,
      "macd_short_window": 12,
      "macd_long_window": 26,
      "macd_signal_window": 9,
      "rsi_period": 14,
      "min_order_sizes": {
        "buy": 0.01,
        "sell": 0.0001
      }
    },
    "XRP": {
      "enabled": true,
      "buy_percentage": -5,
      "sell_percentage": 5,
      "volatility_window": 15,
      "trend_window": 26,
      "min_order_sizes": {
        "buy": 0.01,
        "sell": 1
      }
    },
    "DOGE": {
      "enabled": false,
      "buy_percentage": -4,
      "sell_percentage": 4,
      "volatility_window": 10,
      "trend_window": 20,
      "min_order_sizes": {
        "buy": 0.01,
        "sell": 1
      }
    },
    "SOL": {
      "enabled": true,
      "buy_percentage": -2,
      "sell_percentage": 2,
      "volatility_window": 5,
      "trend_window": 26,
      "min_order_sizes": {
        "buy": 0.01,
        "sell": 0.01
      }
    }
  }
}
```

The PostgreSQL table structure is expected as:
```sql
CREATE TABLE trading_state (
    symbol TEXT PRIMARY KEY,
    initial_price REAL,
    total_trades INTEGER,
    total_profit REAL
);

CREATE TABLE price_history (
    symbol TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    price REAL,
    PRIMARY KEY (symbol, timestamp)
);

CREATE INDEX idx_symbol_timestamp ON price_history (symbol, timestamp);
```
Example output:

```
🔍 Monitoring ETH... Initial Price: $2667.15
🔍 Monitoring XRP... Initial Price: $2.45
💰 Available Balances:
  - ETH: 61.07145081738762922
  - XRP: 630.2
  - SOL: 720.7
  - USDC: 310.3975527322856
📈 ETH Price: $2667.05 (-3.03%)
📊 Expected Buy Price for ETH: $2667.90
📊 Expected Sell Price for ETH: $2832.94
💰 Buying 0.0001 ETH!
🚫 Buy order too small: $0.00 (minimum: $0.01)
📊 ETH Performance - Total Trades: 12 | Total Profit: $815.00
📈 XRP Price: $2.43 (2.40%)
📊 Expected Buy Price for XRP: $2.25
📊 Expected Sell Price for XRP: $2.49
📊 XRP Performance - Total Trades: 0 | Total Profit: $0.00
📈 SOL Price: $200.59 (5.57%)
📊 Expected Buy Price for SOL: $186.21
📊 Expected Sell Price for SOL: $193.81
📊 SOL Performance - Total Trades: 0 | Total Profit: $0.00
```

The included `cb-trading-dashboard.py` can be run seperatly to provide (simple) dashboard for monitoring the price history.

## More basic scripts

### cb-trading-percentage.py
The *most simple* one, It does not keep state, nor any advanced calculations.\
✅ Monitors ETH price every 30 sec\
✅ If ETH drops by buy_percentage (-3%) → BUYS ETH\
✅ If ETH rises by sell_percentage (3%) → SELLS ETH\
✅ Uses market orders for instant execution.\
✅ No database backend needed.

✔ Displays ETH & USDC Balances 💰\
✔ Prevents Trades if You Have No Balance 🚫\
✔ Still Trades ETH & USDC Based on Price Changes 📊\
✔ Trades a percentage of your available ETH or USDC balance.
✔ *Minimum Order*: Makes sure an order meets Coinbase's minimum amounts.

### cb-trading-advanced.py
Similar as the `cb-trading-percentage.py` but also includes:\

✔ *Dynamic Thresholds*: The buy/sell thresholds are adjusted based on recent price volatility.\
✔ *Trend Filter*: Trades are only executed if the price is close to the moving average, avoiding trades during strong trends.\
✔ *Stop-Loss*: A stop-loss mechanism is added to limit losses if the price drops significantly.\
✔ *Performance Tracking*: Tracks the total number of trades and cumulative profit/loss.

### cb-trading-multiple.py
Similar as the `cb-trading-advanced.py` but also includes:\

✔ *Supports Multiple Cryptocurrencies*: The script monitors and trades all cryptocurrencies specified in the `crypto_symbols` list.\
✔ *Independent Tracking for Each Cryptocurrency*: Each cryptocurrency has its own `price_history`, `initial_price`, `total_trades`, and `total_profit` tracking.\
✔ *Keeps State*: Can reuse values like `initial_price`, `price_history`, `total_trades`, and `total_profit` if it gets restarted.

To keep state, a `state.json` is created (if none exists) as:
```json
{
  "ETH": {
    "price_history": [2000.0, 1980.0, 1990.0],
    "initial_price": 2000.0,
    "total_trades": 2,
    "total_profit": 20.0
  },
  "XRP": {
    "price_history": [0.5, 0.49, 0.48],
    "initial_price": 0.5,
    "total_trades": 1,
    "total_profit": -0.02
  }
}
```

## Example Outputs
```
🔍 Monitoring ETH... Initial Price: $3000.00
💰 Available Balance - ETH: 1.5 | USDC: 1000.00
📈 ETH Price: $2910.00 (-3.00%)
🚫 Buy order too small: $0.01 (minimum: $0.01)
💰 Buying 0.0344 ETH!
✅ BUY Order Placed: abc1234

💰 Available Balance - ETH: 1.6 | USDC: 970.00
📈 ETH Price: $3090.00 (3.00%)
💵 Selling 0.1600 ETH!
✅ SELL Order Placed: xyz5678
🚫 Sell order too small: 0.000050 ETH (minimum: 0.000100 ETH)
🚨 Stop-loss triggered! Selling 0.2739 ETH!
📊 Total Trades: 12 | Total Profit: $541.20

💰 Available Balances:
  - ETH: 730.041680797387629226
  - XRP: 40.2
  - DOGE: 640.5
  - SOL: 210.1
  - USDC: 79.3424226884312

📈 ETH Price: $1980.00 (-1.00%)
📊 Expected Buy Price for ETH: $1940.00
📊 Expected Sell Price for ETH: $2060.00
```

### cb-trading-rsi.py
Similar as the `cb-trading-advanced.py` but also includes:

✔ *Supports Multiple Cryptocurrencies*: Enabled/disabled is taked from the `config.json` file (see the template file).
