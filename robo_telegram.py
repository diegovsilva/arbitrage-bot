import socketio
import time
import logging
import os
import requests
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Constantes globais
SALDO_INICIAL_USD = 50.0
LUCRO_MINIMO_PERCENTUAL = 1.30
LUCRO_MAXIMO_PERCENTUAL = 200.0
MUDANCA_MINIMA_PERCENTUAL = 0.005
MUDANCA_MINIMA_LUCRO = 0.50

# Configuração do WebSocket
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'http://localhost:5000')

# Configuração do Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Taxas das exchanges
TAXAS_EXCHANGES = {
    # "BINANCE": 0.001,
    "KRAKEN": 0.0026,
    "MEXC": 0.001,
    "GATE": 0.002
}

# Configuração do banco de dados SQLite
DB_PATH = "arbitragem.db"

# Links das moedas para cada exchange
LINKS_EXCHANGES = {
    # "BINANCE": "https://www.binance.com/en/trade/{moeda}_USDT",
    "KRAKEN": "https://pro.kraken.com/app/trade/{moeda}-usd", 
    "MEXC": "https://www.mexc.com/exchange/{moeda}_USDT",
    "GATE": "https://www.gate.io/trade/{moeda}_USDT"
}

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'robo_{datetime.today().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

# Cliente WebSocket
sio = socketio.Client()


class DatabaseManager:
    """Gerenciador de operações no banco de dados SQLite."""
    def __init__(self, db_path):
        self.db_path = db_path

    def conectar(self):
        return sqlite3.connect(self.db_path)

    def inicializar_tabelas(self):
        """Cria as tabelas no banco de dados, se não existirem."""
        with self.conectar() as conexao:
            cursor = conexao.cursor()
            # Tabela para oportunidades
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
            # Tabela para mensagens enviadas
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS mensagens_enviadas (
                moeda TEXT,
                compra_exchange TEXT,
                venda_exchange TEXT,
                preco_compra TEXT,
                preco_venda TEXT,
                diferenca_percentual TEXT,
                quantidade TEXT,
                lucro_liquido TEXT,
                data_hora TEXT,
                UNIQUE(moeda, compra_exchange, venda_exchange, preco_compra, preco_venda, diferenca_percentual, quantidade, lucro_liquido, data_hora)
            )
            ''')
            conexao.commit()

    def obter_ultima_oportunidade(self, moeda):
        """Retorna a última oportunidade registrada para a moeda."""
        with self.conectar() as conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT * FROM oportunidades WHERE moeda = ?", (moeda,))
            resultado = cursor.fetchone()
            if resultado:
                return resultado
            return None

    def salvar_oportunidade(self, moeda, compra_exchange, venda_exchange, preco_compra, preco_venda, lucro_liquido):
        """Salva ou atualiza uma oportunidade no banco de dados."""
        with self.conectar() as conexao:
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

    def verificar_mensagem_enviada(self, parametros):
        """Verifica se uma mensagem com os mesmos parâmetros já foi enviada."""
        with self.conectar() as conexao:
            cursor = conexao.cursor()
            cursor.execute('''
            SELECT * FROM mensagens_enviadas WHERE
                moeda = ? AND
                compra_exchange = ? AND
                venda_exchange = ? AND
                preco_compra = ? AND
                preco_venda = ? AND
                diferenca_percentual = ? AND
                quantidade = ? AND
                lucro_liquido = ? AND
                data_hora = ?
            ''', parametros)
            return cursor.fetchone() is not None

    def registrar_mensagem_enviada(self, parametros):
        """Registra uma mensagem como enviada no banco de dados."""
        with self.conectar() as conexao:
            cursor = conexao.cursor()
            try:
                cursor.execute('''
                INSERT INTO mensagens_enviadas (
                    moeda, compra_exchange, venda_exchange, preco_compra, preco_venda,
                    diferenca_percentual, quantidade, lucro_liquido, data_hora
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', parametros)
                conexao.commit()
            except sqlite3.IntegrityError:
                # Ignora tentativas de inserir duplicatas
                pass

    def limpar_mensagens_antigas(self, dias=7):
        """Remove mensagens enviadas há mais de `dias` dias."""
        with self.conectar() as conexao:
            cursor = conexao.cursor()
            cursor.execute('''
            DELETE FROM mensagens_enviadas WHERE data_hora < ?
            ''', (datetime.now() - timedelta(days=dias),))
            conexao.commit()


def log_info(message):
    """Centraliza logs informativos."""
    logging.info(message)


def log_warning(message):
    """Centraliza logs de aviso."""
    logging.warning(message)


def log_error(message):
    """Centraliza logs de erro."""
    logging.error(message)


def enviar_mensagem_telegram(mensagem, moeda, melhor_compra, melhor_venda):
    """Envia uma mensagem ao Telegram com links das moedas nas exchanges."""
    # Obter os links das moedas nas exchanges
    link_compra = LINKS_EXCHANGES.get(melhor_compra.upper(), "").format(moeda=moeda.split("/")[0])
    link_venda = LINKS_EXCHANGES.get(melhor_venda.upper(), "").format(moeda=moeda.split("/")[0])

    # Adicionar os links à mensagem
    mensagem_com_links = (
        f"{mensagem}\n\n"
        f"🔗 [Comprar na {melhor_compra}]({link_compra})\n"
        f"🔗 [Vender na {melhor_venda}]({link_venda})"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem_com_links,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log_error(f"Erro ao enviar mensagem: {e}")


def calcular_lucro_liquido(quantidade, preco_compra, preco_venda, taxa_compra, taxa_venda):
    """Calcula o lucro líquido considerando taxas."""
    custo_total = quantidade * preco_compra * (1 + taxa_compra)
    receita_total = quantidade * preco_venda * (1 - taxa_venda)
    return receita_total - custo_total


def realizar_arbitragem(db_manager, moeda, precos):
    """Verifica a melhor arbitragem e usa banco de dados para filtrar mensagens repetidas."""
    log_info(f"Analisando arbitragem para {moeda}...")
    if not precos:
        log_warning(f"Nenhum preço disponível para {moeda}.")
        return

    try:
        melhor_compra = min(precos, key=precos.get)
        melhor_venda = max(precos, key=precos.get)
    except ValueError as e:
        log_error(f"Erro ao determinar melhor compra/venda: {e}")
        return

    preco_compra = precos[melhor_compra]
    preco_venda = precos[melhor_venda]

    if preco_compra >= preco_venda:
        log_info(f"Sem arbitragem viável para {moeda}")
        return

    taxa_compra = TAXAS_EXCHANGES.get(melhor_compra.upper(), 0)
    taxa_venda = TAXAS_EXCHANGES.get(melhor_venda.upper(), 0)
    quantidade = SALDO_INICIAL_USD / preco_compra
    lucro_liquido = calcular_lucro_liquido(quantidade, preco_compra, preco_venda, taxa_compra, taxa_venda)
    diferenca_percentual = float(((preco_venda - preco_compra) / preco_compra) * 100)

    if diferenca_percentual < float(LUCRO_MINIMO_PERCENTUAL) or diferenca_percentual >= float(LUCRO_MAXIMO_PERCENTUAL):
        log_info(f"Oportunidade para {moeda} com lucro de {diferenca_percentual:.2f}% é menor que {LUCRO_MINIMO_PERCENTUAL}%, ignorando.")
        return

    ultima_oportunidade = db_manager.obter_ultima_oportunidade(moeda)
    if ultima_oportunidade:
        _, _, _, ultima_compra, ultima_venda, ultimo_lucro, _ = ultima_oportunidade
        if (abs(preco_compra - ultima_compra) / ultima_compra < MUDANCA_MINIMA_PERCENTUAL and
            abs(preco_venda - ultima_venda) / ultima_venda < MUDANCA_MINIMA_PERCENTUAL and
            abs(lucro_liquido - ultimo_lucro) < MUDANCA_MINIMA_LUCRO):
            log_info(f"Oportunidade para {moeda} não mudou significativamente, ignorando.")
            return

    data_hora_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')[:-3]  # Formato: YYYY-MM-DD HH:MM:SS.sss
    parametros = (
        moeda, melhor_compra, melhor_venda, preco_compra, preco_venda,
        diferenca_percentual, quantidade, lucro_liquido, data_hora_atual
    )

    if db_manager.verificar_mensagem_enviada(parametros):
        log_info(f"Mensagem para {moeda} já foi enviada anteriormente, ignorando.")
        return

    mensagem = (
        f"🚀 *Oportunidade de Arbitragem!* 🚀\n\n"
        f"*Moeda:* `{moeda}`\n"
        f"💰 *Compra na {melhor_compra}:* `${preco_compra:.6f}`\n"
        f"📈 *Venda na {melhor_venda}:* `${preco_venda:.6f}`\n"
        f"📊 *Diferença Percentual:* `{diferenca_percentual:.2f}%`\n\n"
        f"🛒 *Quantidade Comprada:* `{quantidade:.6f}`\n"
        f"💸 *Lucro Líquido:* `${lucro_liquido:.2f}`\n"
        f"📅 *Data/Hora:* `{data_hora_atual}`"
    )

    log_info(f"Enviando nova oportunidade para {moeda}")
    enviar_mensagem_telegram(mensagem, moeda, melhor_compra, melhor_venda)
    db_manager.registrar_mensagem_enviada(parametros)
    db_manager.salvar_oportunidade(moeda, melhor_compra, melhor_venda, preco_compra, preco_venda, lucro_liquido)


@sio.on('preco_atualizado')
def processar_arbitragem_evento(dados):
    """Atualiza os preços e verifica oportunidades de arbitragem."""
    global precos_exchanges
    exchange = dados['exchange']
    moeda = dados['moeda']
    preco = dados['preco']
    if moeda not in precos_exchanges:
        precos_exchanges[moeda] = {}
    precos_exchanges[moeda][exchange] = preco
    if len(precos_exchanges[moeda]) >= 2:
        realizar_arbitragem(db_manager, moeda, precos_exchanges[moeda])


def conectar_websocket():
    """Conecta ao WebSocket e tenta reconectar em caso de falha."""
    max_tentativas = 5
    tentativas = 0
    while tentativas < max_tentativas:
        try:
            log_info("Conectando ao WebSocket...")
            sio.connect(WEBHOOK_URL)
            log_info("Conexão estabelecida.")
            sio.wait()
        except Exception as e:
            tentativas += 1
            log_error(f"Erro na conexão WebSocket: {e}")
            log_info(f"Tentando reconectar em 5 segundos... (Tentativa {tentativas}/{max_tentativas})")
            time.sleep(5)
    log_error("Número máximo de tentativas atingido. Encerrando...")


if __name__ == "__main__":
    db_manager = DatabaseManager(DB_PATH)
    db_manager.inicializar_tabelas()
    db_manager.limpar_mensagens_antigas()  # Limpa mensagens antigas ao iniciar
    precos_exchanges = {}
    conectar_websocket()