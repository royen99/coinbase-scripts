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
