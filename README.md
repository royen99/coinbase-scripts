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

🔍 **Trading Logic Buy**: Depending on the buy/thresholds set, it would perform a (buy) trade if:
- The price change <= The dynamic buy threshold and
- A positive MACD Buy Signal and
- At least 5 MACD (buy) Confirmations are set and
- RSI is below 30 and
- Current Price is *lower* then the Long Term Moiving average and
- There is Sufficient balance for USDC to meet the minimum trade amount.

🔍 **Trading Logic Sell**: Depending on the buy/thresholds set, it would perform a (buy) trade if:
- The price change >= The dynamic buy threshold and
- A positive MACD Sell Signal and
- At least 5 MACD (sell) Confirmations are set and
- RSI is above 70 and
- Current Price is *higher* then the Long Term Moiving average and
- There is Sufficient balance for the crypto currency to meet the minimum trade amount.

🚨 Note that the various indicators will only function with enough data points (depending on your settings).\
Without enough price history you will see log lines such as:\
⚠️ LTC: Not enough data for indicators. Required: 51, Available: 46.\
⚠️ ETH: Not enough data for long-term MA. Skipping.

🔄 **Testing Stratagy**: The `main` branch of this project is running 24/7 against an actual Coinbase wallet, doing actual trades (with a moderate sized wallet) with currently the following coins enabled:
- ETH
- XRP
- DOGE
- SOL
- GODS
- BONK
- HONEY
- MATIC
- LTC

Additional settings (inside the `config.json`) are needed holding your database info and which coins you want to enable/disable.\
You can adjust `trade_percentage` to control how much of your balance gets traded. 😘💸\
**Fine-Tune Parameters**: Adjust the `volatility_window`, `trend_window`, and `stop_loss_percentage` to suit your risk tolerance and market conditions. 📊

```json
{
  "name": "organizations/{org_id}/apiKeys/{key_id}",
  "privateKey": "-----BEGIN EC PRIVATE KEY-----\nYOUR PRIVATE KEY\n-----END EC PRIVATE KEY-----\n",
  "buy_percentage": 10,
  "sell_percentage": 10,
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
      "buy_percentage": -4,
      "sell_percentage": 5,
      "volatility_window": 20,
      "trend_window": 200,
      "macd_short_window": 12,
      "macd_long_window": 26,
      "macd_signal_window": 9,
      "rsi_period": 50,
      "min_order_sizes": {
        "buy": 0.01,
        "sell": 0.001
      },
      "precision": {
        "price": 2,
        "amount": 6
      }
    },
    "XRP": {
      "enabled": true,
      "buy_percentage": -5,
      "sell_percentage": 5,
      "volatility_window": 20,
      "trend_window": 200,
      "macd_short_window": 12,
      "macd_long_window": 26,
      "macd_signal_window": 9,
      "rsi_period": 50,

      "min_order_sizes": {
        "buy": 1,
        "sell": 1
      },
      "precision": {
        "price": 2,
        "amount": 6
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

CREATE TABLE balances (
    currency TEXT PRIMARY KEY,
    available_balance REAL
);

CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    symbol TEXT,
    side TEXT,
    amount REAL,
    price REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
📈 ETH Price: $2757.07 (0.26%)
📊 ETH Indicators - Volatility: 0.0009, Moving Avg: 2725.5225, MACD: -4.2645, Signal: -4.4649, RSI: 64.10
📊 Expected Buy Price for ETH: $2639.902765 (Dynamic Buy Threshold: -4.00%)
📊 Expected Sell Price for ETH: $2887.621544 (Dynamic Sell Threshold: 5.00%)
📊 ETH Trading Signals - MACD Buy: True, RSI Buy: False, MACD Sell: False, RSI Sell: False
📊 ETH MACD Confirmation - Buy: 15, Sell: 3
📊 ETH Performance - Total Trades: 6 | Total Profit: $270.52
```

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
✔ Trades a percentage of your available ETH or USDC balance.\
✔ *Minimum Order*: Makes sure an order meets Coinbase's minimum amounts.

### [EXPERIMENTAL] cb-trading-ai.py
Almost similar as the `cb-trading-db.py` but:

✔ *AI LLM Decision*: Instead of using the MACD/RSI indicators, these are fed to an ollama backend.

There is still a failsafe that would perform an actual trade based on the buy/sell threshold set in the `config.json`.\
The AI part is far from stable and (during testing) using a basic `mistral` model.
