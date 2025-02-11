import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
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

# Initialize Dash app with Bootstrap
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Layout of the dashboard
app.layout = dbc.Container([
    # Navbar
    dbc.NavbarSimple(
        brand="Crypto Trading Bot Dashboard",
        color="primary",
        dark=True,
    ),

    # Dropdown to select coin
    dbc.Row([
        dbc.Col([
            html.Label("Select Coin:"),
            dcc.Dropdown(
                id="coin-dropdown",
                options=[{"label": coin, "value": coin} for coin in enabled_coins],
                value=enabled_coins[0] if enabled_coins else None,  # Default to the first enabled coin
                clearable=False
            ),
        ], width=4),
    ], className="mt-4"),

    # Tabs for different sections
    dbc.Tabs([
        # Price Trend Tab
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id="price-chart"),
                ], width=12),
            ], className="mt-4"),

            dbc.Row([
                dbc.Col([
                    html.H4("Expected Buy/Sell Prices"),
                    html.Div(id="expected-prices"),
                ], width=6),
            ], className="mt-4"),
        ], label="Price Trend"),

        # Performance Metrics Tab
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H4("Performance Metrics"),
                    html.Div(id="performance-metrics"),
                ], width=6),
            ], className="mt-4"),
        ], label="Performance"),

        # Trade Log Tab
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H4("Recent Trades"),
                    html.Div(id="trade-log"),
                ], width=12),
            ], className="mt-4"),
        ], label="Trade Log"),

        # Balance and Portfolio Tab
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H4("Balance and Portfolio"),
                    html.Div(id="balance-portfolio"),
                ], width=12),
            ], className="mt-4"),
        ], label="Balances"),
    ]),

    # Interval component for real-time updates
    dcc.Interval(id="interval-component", interval=30 * 1000, n_intervals=0),  # Update every 30 seconds
], fluid=True)

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

# Callback to update expected buy/sell prices
@app.callback(
    Output("expected-prices", "children"),
    Input("interval-component", "n_intervals"),
    Input("coin-dropdown", "value")
)
def update_expected_prices(n, selected_coin):
    # Fetch expected buy/sell prices from the bot's configuration
    coin_settings = config["coins"][selected_coin]
    buy_threshold = coin_settings["buy_percentage"]
    sell_threshold = coin_settings["sell_percentage"]

    # Fetch the current price
    query = f"SELECT price FROM price_history WHERE symbol = '{selected_coin}' ORDER BY timestamp DESC LIMIT 1"
    with engine.connect() as connection:
        current_price = connection.execute(db.text(query)).fetchone()[0]

    # Calculate expected buy/sell prices
    expected_buy_price = current_price * (1 + buy_threshold / 100)
    expected_sell_price = current_price * (1 + sell_threshold / 100)

    # Display expected prices
    return html.Div([
        html.P(f"Expected Buy Price: ${expected_buy_price:.2f}"),
        html.P(f"Expected Sell Price: ${expected_sell_price:.2f}"),
    ])

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
        return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True)

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
            html.P(f"Total Trades: {result[0]}"),
            html.P(f"Total Profit: ${result[1]:.2f}"),
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
        return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True)

# Run the app
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=True)
