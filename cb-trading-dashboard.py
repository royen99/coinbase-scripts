from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
import time
import random  # Replace with actual API calls for real data

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

def price_updater():
    while True:
        # Simulate fetching real-time prices (Replace with real API calls)
        price_data = {
            "BTC": round(random.uniform(30000, 40000), 2),
            "ETH": round(random.uniform(2000, 3000), 2),
            "LTC": round(random.uniform(100, 200), 2)
        }
        socketio.emit('update_prices', price_data)
        time.sleep(2)  # Adjust update frequency as needed

if __name__ == '__main__':
    threading.Thread(target=price_updater, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000)
