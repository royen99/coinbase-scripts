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

# Initialize Dash app
app = dash.Dash(__name__)

# Layout of the dashboard
app.layout = html.Div([
    html.H1("Crypto Trading Bot Dashboard", style={"textAlign": "center"}),
    
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
    Input("interval-component", "n_intervals")
)
def update_price_chart(n):
    # Fetch price history from the database
    query = "SELECT timestamp, price FROM price_history WHERE symbol = 'ETH' ORDER BY timestamp DESC LIMIT 100"
    df = pd.read_sql(query, engine)

    # Create the price chart
    figure = {
        "data": [go.Scatter(x=df["timestamp"], y=df["price"], mode="lines", name="ETH Price")],
        "layout": go.Layout(title="ETH Price History", xaxis={"title": "Time"}, yaxis={"title": "Price"})
    }
    return figure

# Callback to update the trade log
@app.callback(
    Output("trade-log", "children"),
    Input("interval-component", "n_intervals")
)
def update_trade_log(n):
    # Fetch recent trades from the database
    query = "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10"
    df = pd.read_sql(query, engine)

    # Display the trade log
    return html.Table([
        html.Thead(html.Tr([html.Th(col) for col in df.columns])),
        html.Tbody([html.Tr([html.Td(df.iloc[i][col]) for col in df.columns]) for i in range(len(df))])
    ])

# Callback to update performance metrics
@app.callback(
    Output("performance-metrics", "children"),
    Input("interval-component", "n_intervals")
)
def update_performance_metrics(n):
    # Fetch performance metrics from the database
    query = "SELECT total_trades, total_profit FROM trading_state WHERE symbol = 'ETH'"
    result = engine.execute(query).fetchone()

    # Display performance metrics
    return html.Div([
        html.P(f"Total Trades: {result['total_trades']}"),
        html.P(f"Total Profit: ${result['total_profit']:.2f}"),
    ])

# Callback to update balance and portfolio
@app.callback(
    Output("balance-portfolio", "children"),
    Input("interval-component", "n_intervals")
)
def update_balance_portfolio(n):
    # Fetch balances from the database
    query = "SELECT currency, available_balance FROM balances"
    df = pd.read_sql(query, engine)

    # Display balance and portfolio
    return html.Table([
        html.Thead(html.Tr([html.Th(col) for col in df.columns])),
        html.Tbody([html.Tr([html.Td(df.iloc[i][col]) for col in df.columns]) for i in range(len(df))])
    ])

# Run the app
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=True)
