# db.py
import json
import psycopg2
from psycopg2.extras import RealDictCursor

def load_config():
    with open("config.json") as f:
        return json.load(f)

def get_db_connection():
    config = load_config()
    db = config["database"]
    conn = psycopg2.connect(
        host=db["host"],
        port=db["port"],
        database=db["name"],
        user=db["user"],
        password=db["password"]
    )
    return conn
