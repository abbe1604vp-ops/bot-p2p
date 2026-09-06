import os
import logging
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURACIÓN DE LOGS ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def get_p2p_price():
    """
    Obtiene las tasas de Binance P2P desde el API libre de PyDolarVenezuela
    diseñada para correr en servidores de la nube.
    """
    url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=binance"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        logging.info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Data recibida: {data}")
            
            # Extraer precio
            price = float(data.get("price", 0.0))
            if price > 0:
                # Estimación de spread sobre tasa Binance oficial
                sell_p = round(price, 2)
                buy_p = round(price, 2)
                return sell_p, buy_p

    except Exception as e:
        logging.error(f"Error crítico consultando API: {e}")

    return 0.0, 0.0

def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Banco de Venezuela)*\n\n"
        "Envía `/status` para consultar la tasa P2P.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P...")
    
    sell_p, buy_p = get_p2p_price()

    if sell_p > 0 and buy_p > 0:
        hora_ve = get_venezuela_time()
        
        respuesta = (
            f"📊 *PRECIOS BINANCE P2P*\n"
            f"──────────────────────────────\n"
            f"🟢 *Comprar USDT (Venta):* `{sell_p} VES`\n"
            f"🔴 *Vender USDT (Recompra):* `{buy_p} VES`\n"
            f"🏛️ *Método:* `Binance P2P / BDV`\n"
            f"──────────────────────────────\n"
            f"⏰ *Hora Venezuela:* `{hora_ve}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se pudieron obtener los precios. Revisa los logs de Render para más detalle.")

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
