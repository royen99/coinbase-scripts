import dash
from dash import dcc, html
import plotly.express as px
import psycopg2
import json

# Load configuration from config.json
with open("config.json", "r") as f:
    config = json.load(f)

# Database connection parameters
DB_HOST = config["database"]["host"]
DB_PORT = config["database"]["port"]
DB_NAME = config["database"]["name"]
DB_USER = config["database"]["user"]
DB_PASSWORD = config["database"]["password"]

def get_db_connection():
    """Connect to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

# Create Dash app
app = dash.Dash(__name__)

# Layout of the dashboard
app.layout = html.Div([
    dcc.Dropdown(
        id="coin-dropdown",
        options=[{"label": symbol, "value": symbol} for symbol in config["coins"].keys()],
        value="ETH",  # Default selected coin
        clearable=False
    ),
    dcc.Graph(id="price-chart"),
    dcc.Interval(id="interval", interval=5000)  # Refresh every 5 seconds
])

# Callback to update the chart
@app.callback(
    dash.dependencies.Output("price-chart", "figure"),
    dash.dependencies.Input("interval", "n_intervals"),
    dash.dependencies.Input("coin-dropdown", "value")
)
def update_chart(n, selected_coin):
    # Fetch price history from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT price_history FROM trading_state WHERE symbol = %s", (selected_coin,))
        row = cursor.fetchone()
        if row:
            price_history = row[0]
            fig = px.line(price_history, title=f"{selected_coin} Price History")
            return fig
        return {}
    except Exception as e:
        print(f"Error fetching data from database: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()

# Run the dashboard
if __name__ == "__main__":
    app.run_server(host='0.0.0.0', port=8050, debug=True)
