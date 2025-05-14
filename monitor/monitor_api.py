# monitor_api.py
from fastapi import APIRouter, HTTPException
from db import get_db_connection, load_config
from psycopg2.extras import RealDictCursor

router = APIRouter()

@router.get("/config")
def get_config():
    return load_config()

@router.get("/enabled-coins")
def get_enabled_coins():
    """Return list of enabled coins from config"""
    config = load_config()
    coins = config.get("coins", {})
    enabled = [symbol for symbol, settings in coins.items() if settings.get("enabled")]
    return enabled

@router.get("/prices/{symbol}")
def get_prices(symbol: str):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT timestamp, price 
                FROM price_history 
                WHERE symbol = %s 
                ORDER BY timestamp DESC 
                LIMIT 200
            """, (symbol,))
            rows = cur.fetchall()
            return list(reversed(rows))
    except Exception as e:
        print(f"[ERROR] get_prices({symbol}):", e)  # 👈 log the error
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/signals/{symbol}")
def get_signals(symbol: str):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT timestamp, side AS action, price 
                FROM trades 
                WHERE symbol = %s 
                ORDER BY timestamp ASC
            """, (symbol,))
            return cur.fetchall()
    except Exception as e:
        print(f"[ERROR] get_signals({symbol}):", e)  # 👈 log the error
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/trading_state/{symbol}")
def get_trading_state(symbol: str):
    """Get current trading state like initial price and total profit"""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM trading_state 
                WHERE symbol = %s
            """, (symbol,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Symbol not found")
            return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/balances")
def get_balances():
    """Get current available balances"""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM balances
            """)
            return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/indicators/{symbol}")
def get_indicators(symbol: str):
    """Returns current price and simple moving average"""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT price 
                FROM price_history 
                WHERE symbol = %s 
                ORDER BY timestamp DESC 
                LIMIT 50
            """, (symbol,))
            rows = cur.fetchall()
            prices = [row['price'] for row in rows]
            if not prices:
                raise HTTPException(status_code=404, detail="No price data found")
            current_price = prices[0]
            moving_average = sum(prices) / len(prices)
            return {
                "current_price": current_price,
                "moving_average": round(moving_average, 4)
            }
    except Exception as e:
        print(f"[ERROR] get_indicators({symbol}):", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/recent-trades")
def get_recent_trades():
    """Return last 25 trades across all coins"""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT symbol, side, price, amount, timestamp
                FROM trades
                ORDER BY timestamp DESC
                LIMIT 25
            """)
            return cur.fetchall()
    except Exception as e:
        print(f"[ERROR] get_recent_trades():", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

def get_weighted_avg_buy_price(symbol: str):
    """Compute weighted average buy price since last sell."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Step 1: Get timestamp of last SELL
        cur.execute("""
            SELECT timestamp FROM trades 
            WHERE symbol = %s AND side = 'SELL' 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (symbol,))
        last_sell = cur.fetchone()
        last_sell_time = last_sell[0] if last_sell else None

        # Step 2: Get all BUYs after last SELL
        if last_sell_time:
            cur.execute("""
                SELECT amount, price FROM trades 
                WHERE symbol = %s AND side = 'BUY' 
                AND timestamp > %s
            """, (symbol, last_sell_time))
        else:
            cur.execute("""
                SELECT amount, price FROM trades 
                WHERE symbol = %s AND side = 'BUY'
            """, (symbol,))
        
        buy_trades = cur.fetchall()

        if not buy_trades:
            return None

        total_amount = sum(t[0] for t in buy_trades)
        if total_amount == 0:
            return None

        weighted_avg = sum(t[0] * t[1] for t in buy_trades) / total_amount
        return round(weighted_avg, 8)

    except Exception as e:
        print(f"[ERROR] Weighted Avg for {symbol}: {e}")
        return None
    finally:
        cur.close()
        conn.close()

@router.get("/avg-buy-price/{symbol}")
def avg_buy_price(symbol: str):
    price = get_weighted_avg_buy_price(symbol)
    return { "symbol": symbol, "avg_buy_price": price }
