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

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'webhook_{datetime.today().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # Permitir conexões de qualquer origem

# Configuração das exchanges
EXCHANGES = {
    "binance": ccxt.binance({'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_SECRET')}),
    "kraken": ccxt.kraken({'apiKey': os.getenv('KRAKEN_API_KEY'), 'secret': os.getenv('KRAKEN_SECRET')}),
    "gate": ccxt.gateio(),
    "mexc": ccxt.mexc()
}


# Lista de moedas para monitorar
MOEDAS = os.getenv('MOEDAS', "").split(',')

# Intervalo de busca em segundos
INTERVALO_BUSCA = int(os.getenv('INTERVALO_BUSCA', 5))

def buscar_preco_exchange(exchange_name, exchange, moeda):
    """Busca o preço de uma moeda em uma exchange específica."""
    for tentativa in range(3):  # Tenta buscar o preço até 3 vezes
        try:
            ticker = exchange.fetch_ticker(moeda)
            preco = ticker.get('last')
            if preco:
                logging.info(f"{exchange_name.upper()} - {moeda}: {preco:.6f}")
                socketio.emit('preco_atualizado', {
                    'exchange': exchange_name.upper(),
                    'moeda': moeda,
                    'preco': preco,
                    'timestamp': datetime.now().isoformat()
                })
            return
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logging.warning(f"Tentativa {tentativa+1}: Erro ao buscar {moeda} em {exchange_name.upper()}: {e}")
            time.sleep(2)  # Espera antes de tentar novamente
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar {moeda} em {exchange_name.upper()}: {e}")
            return

def buscar_precos():
    """Busca os preços de todas as moedas em todas as exchanges utilizando threads."""
    while True:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for moeda in MOEDAS:
                for nome, exchange in EXCHANGES.items():
                    executor.submit(buscar_preco_exchange, nome, exchange, moeda)
        time.sleep(INTERVALO_BUSCA)

# Iniciar a busca de preços em uma thread separada
threading.Thread(target=buscar_precos, daemon=True).start()

@app.route('/')
def index():
    return "Servidor SocketIO para preços de criptomoedas rodando!"

if __name__ == '__main__':
    socketio.run(app, host='localhost', port=5000, debug=True)
