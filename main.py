import os
import logging
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURACIÓN DE LOGS ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- VARIABLE DE ENTORNO ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- CONSULTA A BINANCE P2P (BANCO DE VENEZUELA) ---
def get_p2p_price():
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    # 1. Tasa de Venta (Comprar USDT con Banco de Venezuela)
    payload_sell = {
        "asset": "USDT",
        "fiat": "VES",
        "tradeType": "BUY",
        "page": 1,
        "rows": 5,
        "payTypes": ["BANK_OF_VENEZUELA"]
    }

    # 2. Tasa de Recompra (Vender USDT por Banco de Venezuela)
    payload_buy = {
        "asset": "USDT",
        "fiat": "VES",
        "tradeType": "SELL",
        "page": 1,
        "rows": 5,
        "payTypes": ["BANK_OF_VENEZUELA"]
    }

    try:
        # Petición Venta
        res_sell = requests.post(url, json=payload_sell, headers=headers, timeout=6)
        data_sell = res_sell.json()
        price_sell = float(data_sell["data"][0]["adv"]["price"]) if data_sell.get("data") else 0.0

        # Petición Recompra
        res_buy = requests.post(url, json=payload_buy, headers=headers, timeout=6)
        data_buy = res_buy.json()
        price_buy = float(data_buy["data"][0]["adv"]["price"]) if data_buy.get("data") else 0.0

        return round(price_sell, 2), round(price_buy, 2)
    except Exception as e:
        logging.error(f"Error al consultar Binance P2P: {e}")
        return 0.0, 0.0

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Banco de Venezuela)*\n\n"
        "Envía el comando `/status` para obtener los precios actualizados de compra y venta.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P (Banco de Venezuela)...")
    
    sell_p, buy_p = get_p2p_price()

    if sell_p > 0 and buy_p > 0:
        spread = round(sell_p - buy_p, 2)
        
        respuesta = (
            f"📊 *PRECIOS P2P BINANCE (BANCO DE VENEZUELA)*\n"
            f"──────────────────────────────\n"
            f"🟢 *Comprar USDT (Venta):* `{sell_p} VES`\n"
            f"🔴 *Vender USDT (Recompra):* `{buy_p} VES`\n"
            f"📐 *Spread / Diferencia:* `{spread} VES`\n"
            f"──────────────────────────────\n"
            f"⏰ *Hora de consulta:* `{datetime.now().strftime('%I:%M:%S %p')}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ Error al conectar con la API de Binance P2P. Intenta de nuevo.")

# --- INICIALIZACIÓN Y ARRANQUE ---
def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("No se encontró la variable de entorno TELEGRAM_BOT_TOKEN.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Registrar Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    print("🚀 Bot iniciado correctamente...")
    app.run_polling()

if __name__ == "__main__":
    main()
