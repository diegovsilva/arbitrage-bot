from flask import Flask
from flask_socketio import SocketIO
from datetime import datetime
import ccxt
import threading
import time
import logging
import os
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'webhook_{datetime.today().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

EXCHANGES = {
    "binance": ccxt.binance({'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_SECRET')}),
    "kraken": ccxt.kraken({'apiKey': os.getenv('KRAKEN_API_KEY'), 'secret': os.getenv('KRAKEN_SECRET')}),
    "gate": ccxt.gateio(),
    "mexc": ccxt.mexc()
}

MOEDAS = os.getenv('MOEDAS', "").split(',')
INTERVALO_BUSCA = int(os.getenv('INTERVALO_BUSCA', 5))

def buscar_precos():
    while True:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for moeda in MOEDAS:
                for nome, exchange in EXCHANGES.items():
                    executor.submit(lambda: print(f"Buscando preço {moeda} na {nome}"))
        time.sleep(INTERVALO_BUSCA)

threading.Thread(target=buscar_precos, daemon=True).start()

@app.route('/')
def index():
    return "Servidor WebSocket rodando!"

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
