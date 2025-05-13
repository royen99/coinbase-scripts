# monitor_api.py
from fastapi import APIRouter, HTTPException
from db import get_db_connection, load_config

router = APIRouter()

@router.get("/config")
def get_config():
    return load_config()

@router.get("/prices/{coin}")
def get_prices(coin: str):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT timestamp, price 
                FROM price_history 
                WHERE coin = %s 
                ORDER BY timestamp ASC
            """, (coin,))
            rows = cur.fetchall()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/signals/{coin}")
def get_signals(coin: str):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT timestamp, action, price 
                FROM trades 
                WHERE coin = %s 
                ORDER BY timestamp ASC
            """, (coin,))
            rows = cur.fetchall()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
