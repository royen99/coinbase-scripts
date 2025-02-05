# coinbase-scripts
Coinbase crypto trading API scripts

## How It Works

### cb-trading-percentage.py
Monitors ETH price every 30 sec\
If ETH drops by buy_percentage (-3%) → BUYS ETH\
If ETH rises by sell_percentage (3%) → SELLS ETH\
Uses market orders for instant execution

✔ Displays ETH & USDC Balances 💰\
✔ Prevents Trades if You Have No Balance 🚫\
✔ Still Trades ETH & USDC Based on Price Changes 📊\
✔ Trades a percentage of your available ETH or USDC balance\

## Example Output
```
🔍 Monitoring ETH... Initial Price: $3000.00
💰 Available Balance - ETH: 1.5 | USDC: 1000.00
📈 ETH Price: $2910.00 (-3.00%)
💰 Buying 0.0344 ETH!
✅ BUY Order Placed: abc1234

💰 Available Balance - ETH: 1.6 | USDC: 970.00
📈 ETH Price: $3090.00 (3.00%)
💵 Selling 0.1600 ETH!
✅ SELL Order Placed: xyz5678
```
