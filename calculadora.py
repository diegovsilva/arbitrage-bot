import tkinter as tk
from tkinter import ttk, messagebox
import requests

# Taxas das exchanges
EXCHANGE_FEES = {
    "binance": 0.1 / 100,  # 0.1%
    "kraken": 0.26 / 100,  # 0.26%
    "gate": 0.2 / 100,  # 0.2%
    "mexc": 0.2 / 100  # 0.2%
}

# APIs para preços
EXCHANGE_APIS = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={}",
    "kraken": "https://api.kraken.com/0/public/Ticker?pair={}",
    "gate": "https://api.gateio.ws/api/v4/spot/tickers?currency_pair={}",
    "mexc": "https://api.mexc.com/api/v3/ticker/price?symbol={}"
}

# Ajuste dos pares de moedas
EXCHANGE_PAIRS = {
    "binance": lambda symbol: symbol.upper() + "USDT",
    "kraken": lambda symbol: symbol.upper() + "USDT",
    "gate": lambda symbol: symbol.lower() + "_usdt",
    "mexc": lambda symbol: symbol.upper() + "USDT"
}

def fetch_price(symbol, exchange):
    """Obtém o preço da moeda na exchange selecionada."""
    url = EXCHANGE_APIS[exchange].format(EXCHANGE_PAIRS[exchange](symbol))
    try:
        response = requests.get(url)
        data = response.json()
        if exchange in ["binance", "mexc"]:
            return float(data["price"])
        elif exchange == "kraken":
            return float(data["result"][list(data["result"].keys())[0]]["c"][0])
        elif exchange == "gate":
            return float(data[0]["last"])
    except Exception:
        return None

def calculate_arbitrage():
    """Calcula arbitragem entre exchanges selecionadas."""
    symbol = entry_symbol.get().strip().upper()
    amount = entry_amount.get().strip()
    cost = entry_cost.get().strip()
    manual_price = entry_manual_price.get().strip()
    buy_exchange = buy_exchange_var.get()
    sell_exchange = sell_exchange_var.get()

    if not symbol:
        messagebox.showerror("Erro", "Por favor, insira a moeda desejada.")
        return

    prices = {}
    if manual_price:
        try:
            manual_price = float(manual_price)
            for exchange in EXCHANGE_APIS.keys():
                prices[exchange] = manual_price
        except ValueError:
            messagebox.showerror("Erro", "Preço manual inválido.")
            return
    else:
        for exchange in EXCHANGE_APIS.keys():
            price = fetch_price(symbol, exchange)
            if price:
                prices[exchange] = price

    if len(prices) < 2:
        messagebox.showerror("Erro", "Não foi possível obter preços suficientes.")
        return

    buy_price = prices.get(buy_exchange) if buy_exchange != "Auto" else min(prices.values())
    sell_price = prices.get(sell_exchange) if sell_exchange != "Auto" else max(prices.values())

    if buy_price is None or sell_price is None or buy_price >= sell_price:
        messagebox.showerror("Erro", "Selecione exchanges válidas para compra e venda.")
        return

    if amount:
        amount = float(amount)
        cost = amount * buy_price
    elif cost:
        cost = float(cost)
        amount = cost / buy_price
    else:
        messagebox.showerror("Erro", "Insira a quantidade ou o custo desejado.")
        return

    buy_fee = buy_price * amount * EXCHANGE_FEES[buy_exchange]
    sell_fee = sell_price * amount * EXCHANGE_FEES[sell_exchange]

    total_cost = cost + buy_fee
    gross_profit = (sell_price * amount) - total_cost
    net_profit = gross_profit - sell_fee

    spread = ((sell_price - buy_price) / buy_price) * 100
    gross_profit_pct = (gross_profit / total_cost) * 100
    net_profit_pct = (net_profit / total_cost) * 100

    label_result.config(
        text=f"""
        Comprar em: {buy_exchange.upper()} (${buy_price:.2f})
        Vender em: {sell_exchange.upper()} (${sell_price:.2f})
        Spread: {spread:.2f}%
        Custo Total: ${total_cost:.2f}
        Quantidade Comprada: {amount:.6f} {symbol}
        Lucro Bruto: ${gross_profit:.2f} ({gross_profit_pct:.2f}%)
        Lucro Líquido: ${net_profit:.2f} ({net_profit_pct:.2f}%)
        """
    )

def clear_all():
    """Limpa todos os campos e reset os seletores."""
    entry_symbol.delete(0, tk.END)
    entry_amount.delete(0, tk.END)
    entry_cost.delete(0, tk.END)
    entry_manual_price.delete(0, tk.END)
    buy_exchange_var.set("Auto")
    sell_exchange_var.set("Auto")
    label_result.config(text="")

# Interface Gráfica
root = tk.Tk()
root.title("Calculadora de Arbitragem de Criptomoedas")
root.geometry("450x550")

# Seletor de Moeda
tk.Label(root, text="Moeda (ex: BTC, ETH):").pack()
entry_symbol = tk.Entry(root)
entry_symbol.pack()

# Seletor de Quantidade ou Custo
tk.Label(root, text="Quantidade Comprada (deixe em branco se inserir custo):").pack()
entry_amount = tk.Entry(root)
entry_amount.pack()

tk.Label(root, text="Custo Desejado em USDT (deixe em branco se inserir quantidade):").pack()
entry_cost = tk.Entry(root)
entry_cost.pack()

# Seletor de Exchanges
tk.Label(root, text="Selecionar Exchange de Compra:").pack()
buy_exchange_var = tk.StringVar(value="Auto")
buy_exchange_menu = ttk.Combobox(root, textvariable=buy_exchange_var, values=["Auto", "binance", "kraken", "gate", "mexc"])
buy_exchange_menu.pack()

tk.Label(root, text="Selecionar Exchange de Venda:").pack()
sell_exchange_var = tk.StringVar(value="Auto")
sell_exchange_menu = ttk.Combobox(root, textvariable=sell_exchange_var, values=["Auto", "binance", "kraken", "gate", "mexc"])
sell_exchange_menu.pack()

# Preço Manual
tk.Label(root, text="Preço Manual (opcional, usa esse valor em todas as exchanges):").pack()
entry_manual_price = tk.Entry(root)
entry_manual_price.pack()

# Botões
btn_calculate = tk.Button(root, text="Calcular Arbitragem", command=calculate_arbitrage)
btn_calculate.pack()

btn_clear = tk.Button(root, text="Limpar Tudo", command=clear_all)
btn_clear.pack()

# Resultado
label_result = tk.Label(root, text="", justify="left")
label_result.pack()

root.mainloop()
