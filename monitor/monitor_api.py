# monitor_api.py
from fastapi import APIRouter, HTTPException
from db import get_db_connection, load_config

router = APIRouter()

@router.get("/config")
def get_config():
    return load_config()

@router.get("/prices/{symbol}")
def get_prices(symbol: str):
    """Get the latest 200 price entries for a given coin"""
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
            # Reverse to ascending so the chart flows left → right
            return list(reversed(rows))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/signals/{symbol}")
def get_signals(symbol: str):
    """Get historical trades (buy/sell) for a coin"""
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
