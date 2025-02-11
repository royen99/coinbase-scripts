import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import sqlalchemy as db
import json

# Load configuration from config.json
with open("config.json", "r") as f:
    config = json.load(f)

# Database connection settings
DB_HOST = config["database"]["host"]
DB_PORT = config["database"]["port"]
DB_NAME = config["database"]["name"]
DB_USER = config["database"]["user"]
DB_PASSWORD = config["database"]["password"]

# Create database connection
DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = db.create_engine(DATABASE_URI)

# Get enabled coins from config
enabled_coins = [symbol for symbol, settings in config["coins"].items() if settings.get("enabled", False)]

# Initialize Dash app
app = dash.Dash(__name__)

# Layout of the dashboard
app.layout = html.Div([
    html.H1("Crypto Trading Bot Dashboard", style={"textAlign": "center"}),
    
    # Dropdown to select coin
    html.Label("Select Coin:"),
    dcc.Dropdown(
        id="coin-dropdown",
        options=[{"label": coin, "value": coin} for coin in enabled_coins],
        value=enabled_coins[0] if enabled_coins else None,  # Default to the first enabled coin
        clearable=False
    ),

    # Real-Time Price Chart
    dcc.Graph(id="price-chart"),
    dcc.Interval(id="interval-component", interval=30 * 1000, n_intervals=0),  # Update every 30 seconds
    
    # Trading Activity Log
    html.H3("Recent Trades"),
    html.Div(id="trade-log"),

    # Performance Metrics
    html.H3("Performance Metrics"),
    html.Div(id="performance-metrics"),

    # Balance and Portfolio
    html.H3("Balance and Portfolio"),
    html.Div(id="balance-portfolio"),
])

# Callback to update the price chart
@app.callback(
    Output("price-chart", "figure"),
    Input("interval-component", "n_intervals"),
    Input("coin-dropdown", "value")
)
def update_price_chart(n, selected_coin):
    # Fetch price history from the database
    query = f"SELECT timestamp, price FROM price_history WHERE symbol = '{selected_coin}' ORDER BY timestamp DESC LIMIT 100"
    with engine.connect() as connection:
        df = pd.read_sql(query, connection)

    # Create the price chart
    figure = {
        "data": [go.Scatter(x=df["timestamp"], y=df["price"], mode="lines", name=f"{selected_coin} Price")],
        "layout": go.Layout(title=f"{selected_coin} Price History", xaxis={"title": "Time"}, yaxis={"title": "Price"})
    }
    return figure

# Callback to update the trade log
@app.callback(
    Output("trade-log", "children"),
    Input("interval-component", "n_intervals"),
    Input("coin-dropdown", "value")
)
def update_trade_log(n, selected_coin):
    # Fetch recent trades from the database
    query = f"SELECT * FROM trades WHERE symbol = '{selected_coin}' ORDER BY timestamp DESC LIMIT 10"
    with engine.connect() as connection:
        df = pd.read_sql(query, connection)

    # Display the trade log (or a message if no trades exist)
    if df.empty:
        return html.P("No trades recorded yet.")
    else:
        return html.Table([
            html.Thead(html.Tr([html.Th(col) for col in df.columns])),
            html.Tbody([html.Tr([html.Td(df.iloc[i][col]) for col in df.columns]) for i in range(len(df))])
        ])

# Callback to update performance metrics
@app.callback(
    Output("performance-metrics", "children"),
    Input("interval-component", "n_intervals"),
    Input("coin-dropdown", "value")
)
def update_performance_metrics(n, selected_coin):
    # Fetch performance metrics from the database
    query = f"SELECT total_trades, total_profit FROM trading_state WHERE symbol = '{selected_coin}'"
    with engine.connect() as connection:
        result = connection.execute(db.text(query)).fetchone()

    # Display performance metrics (or a message if no data exists)
    if result is None:
        return html.P("No performance data available.")
    else:
        return html.Div([
            html.P(f"Total Trades: {result[0]}"),  # Access by index
            html.P(f"Total Profit: ${result[1]:.2f}"),  # Access by index
        ])

# Callback to update balance and portfolio
@app.callback(
    Output("balance-portfolio", "children"),
    Input("interval-component", "n_intervals")
)
def update_balance_portfolio(n):
    # Fetch balances from the database
    query = "SELECT currency, available_balance FROM balances"
    with engine.connect() as connection:
        df = pd.read_sql(query, connection)

    # Display balance and portfolio (or a message if no data exists)
    if df.empty:
        return html.P("No balance data available.")
    else:
        return html.Table([
            html.Thead(html.Tr([html.Th(col) for col in df.columns])),
            html.Tbody([html.Tr([html.Td(df.iloc[i][col]) for col in df.columns]) for i in range(len(df))])
        ])

# Run the app
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=True)
