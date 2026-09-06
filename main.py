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

# --- OBTENER TASAS BINANCE P2P ---
def get_p2p_price():
    """Obtiene la tasa de Binance P2P VES usando la API de PyDolarVenezuela."""
    url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=binance"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            # La API retorna el objeto del monitor binance
            price = float(data.get("price", 0.0))
            if price > 0:
                return price
    except Exception as e:
        logging.error(f"Error al consultar API de Binance P2P: {e}")
    
    return 0.0

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Venezuela)*\n\n"
        "Envía el comando `/status` para consultar la tasa P2P Binance actualizada.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando tasa de Binance P2P...")
    
    price = get_p2p_price()

    if price > 0:
        respuesta = (
            f"📊 *PRECIO BINANCE P2P (VES)*\n"
            f"──────────────────────────────\n"
            f"💵 *Tasa Binance:* `{price} VES`\n"
            f"🏛️ *Banco:* `Banco de Venezuela / General`\n"
            f"──────────────────────────────\n"
            f"⏰ *Hora:* `{datetime.now().strftime('%I:%M:%S %p')}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se pudo obtener la tasa en este momento.")

# --- INICIALIZACIÓN ---
def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("No se encontró la variable TELEGRAM_BOT_TOKEN.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    print("🚀 Bot iniciado correctamente...")
    app.run_polling()

if __name__ == "__main__":
    main()
