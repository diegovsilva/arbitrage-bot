import socketio
import time
import logging
import os
import requests
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do WebSocket
sio = socketio.Client()

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'robo_{datetime.today().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

# Configuração do WebSocket
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'http://localhost:5000')

# Configuração do Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Taxas das exchanges
TAXAS_EXCHANGES = {
    "BINANCE": 0.001,  
    "KRAKEN": 0.0026,  
    "MEXC": 0.001,  
    "GATE": 0.002  
}

# Dicionário para armazenar os preços mais recentes
precos_exchanges = {}

# Configuração do banco de dados SQLite
DB_PATH = "arbitragem.db"

def inicializar_banco():
    """Cria a tabela no banco de dados, se não existir"""
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oportunidades (
            moeda TEXT PRIMARY KEY,
            compra_exchange TEXT,
            venda_exchange TEXT,
            preco_compra REAL,
            preco_venda REAL,
            lucro_liquido REAL,
            timestamp TEXT
        )
    ''')
    conexao.commit()
    conexao.close()

def obter_ultima_oportunidade(moeda):
    """Retorna a última oportunidade registrada para a moeda"""
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    cursor.execute("SELECT * FROM oportunidades WHERE moeda = ?", (moeda,))
    resultado = cursor.fetchone()
    conexao.close()
    return resultado

def salvar_oportunidade(moeda, compra_exchange, venda_exchange, preco_compra, preco_venda, lucro_liquido):
    """Salva ou atualiza uma oportunidade no banco de dados"""
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    cursor.execute('''
        INSERT INTO oportunidades (moeda, compra_exchange, venda_exchange, preco_compra, preco_venda, lucro_liquido, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(moeda) DO UPDATE SET
            compra_exchange = excluded.compra_exchange,
            venda_exchange = excluded.venda_exchange,
            preco_compra = excluded.preco_compra,
            preco_venda = excluded.preco_venda,
            lucro_liquido = excluded.lucro_liquido,
            timestamp = excluded.timestamp
    ''', (moeda, compra_exchange, venda_exchange, preco_compra, preco_venda, lucro_liquido, datetime.now().isoformat()))
    conexao.commit()
    conexao.close()

def enviar_mensagem_telegram(mensagem):
    """Envia uma mensagem ao Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao enviar mensagem: {e}")

def calcular_lucro_liquido(quantidade, preco_compra, preco_venda, taxa_compra, taxa_venda):
    """Calcula o lucro líquido considerando taxas"""
    custo_total = quantidade * preco_compra * (1 + taxa_compra)
    receita_total = quantidade * preco_venda * (1 - taxa_venda)
    return receita_total - custo_total

@sio.on('preco_atualizado')
def processar_arbitragem_evento(dados):
    """Atualiza os preços e verifica oportunidades de arbitragem"""
    global precos_exchanges

    exchange = dados['exchange']
    moeda = dados['moeda']
    preco = dados['preco']

    if moeda not in precos_exchanges:
        precos_exchanges[moeda] = {}

    precos_exchanges[moeda][exchange] = preco

    if len(precos_exchanges[moeda]) >= 2:
        realizar_arbitragem(moeda, precos_exchanges[moeda])

def realizar_arbitragem(moeda, precos):
    """Verifica a melhor arbitragem e usa banco de dados para filtrar mensagens repetidas"""
    logging.info(f"Analisando arbitragem para {moeda}...")

    if not precos:
        logging.warning(f"Nenhum preço disponível para {moeda}.")
        return

    try:
        melhor_compra = min(precos, key=precos.get)
        melhor_venda = max(precos, key=precos.get)
    except ValueError as e:
        logging.error(f"Erro ao determinar melhor compra/venda: {e}")
        return

    preco_compra = precos[melhor_compra]
    preco_venda = precos[melhor_venda]

    if preco_compra >= preco_venda:
        logging.info(f"Sem arbitragem viável para {moeda}")
        return

    taxa_compra = TAXAS_EXCHANGES[melhor_compra.upper()]
    taxa_venda = TAXAS_EXCHANGES[melhor_venda.upper()]
    saldo_usd = 50.0  

    quantidade = saldo_usd / preco_compra
    lucro_liquido = calcular_lucro_liquido(quantidade, preco_compra, preco_venda, taxa_compra, taxa_venda)
    diferenca_percentual = ((preco_venda - preco_compra) / preco_compra) * 100

    # Verifica se o percentual de lucro é maior ou igual a 1%
    if diferenca_percentual < 0.7 or diferenca_percentual >= 200.0:
        logging.info(f"Oportunidade para {moeda} com lucro de {diferenca_percentual:.2f}% é menor que 0.70 %, ignorando.")
        return

    ultima_oportunidade = obter_ultima_oportunidade(moeda)

    if ultima_oportunidade:
        _, _, _, ultima_compra, ultima_venda, ultimo_lucro, _ = ultima_oportunidade
        if (abs(preco_compra - ultima_compra) / ultima_compra < 0.005 and 
            abs(preco_venda - ultima_venda) / ultima_venda < 0.005 and 
            abs(lucro_liquido - ultimo_lucro) < 0.50):
            logging.info(f"Oportunidade para {moeda} não mudou significativamente, ignorando.")
            return

    mensagem = (
            f"🚀 *Oportunidade de Arbitragem!* 🚀\n\n"
            f"*Moeda:* `{moeda}`\n"
            f"💰 *Compra na {melhor_compra}:* `${preco_compra:.6f}`\n"
            f"📈 *Venda na {melhor_venda}:* `${preco_venda:.6f}`\n"
            f"📊 *Diferença Percentual:* `{diferenca_percentual:.2f}%`\n\n"
            f"🛒 *Quantidade Comprada:* `{quantidade:.6f}`\n"
            f"💸 *Lucro Líquido:* `${lucro_liquido:.2f}`\n"
            f"📅 *Data/Hora:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )

    logging.info(f"Enviando nova oportunidade para {moeda}")
    enviar_mensagem_telegram(mensagem)
    salvar_oportunidade(moeda, melhor_compra, melhor_venda, preco_compra, preco_venda, lucro_liquido)

def conectar_websocket():
    """Conecta ao WebSocket e tenta reconectar em caso de falha"""
    max_tentativas = 5
    tentativas = 0

    while tentativas < max_tentativas:
        try:
            logging.info("Conectando ao WebSocket...")
            sio.connect(WEBHOOK_URL)
            logging.info("Conexão estabelecida.")
            sio.wait()
        except Exception as e:
            tentativas += 1
            logging.error(f"Erro na conexão WebSocket: {e}")
            logging.info(f"Tentando reconectar em 5 segundos... (Tentativa {tentativas}/{max_tentativas})")
            time.sleep(5)

    logging.error("Número máximo de tentativas atingido. Encerrando...")

if __name__ == "__main__":
    inicializar_banco()
    conectar_websocket()