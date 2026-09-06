import os
import logging
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configuración de Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def get_p2p_price():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # Intento 1: API PyDolarVenezuela (Binance)
    try:
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=binance"
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            price = float(data.get("price", 0.0))
            if price > 0:
                return round(price, 2), round(price, 2)
    except Exception as e:
        logging.error(f"Error en Fuente 1: {e}")

    # Intento 2: API DolarApi (P2P Binance)
    try:
        url2 = "https://ve.dolarapi.com/v1/dolares/p2p/binance"
        res2 = requests.get(url2, headers=headers, timeout=5)
        if res2.status_code == 200:
            data2 = res2.json()
            compra = float(data2.get("compra", 0.0))
            venta = float(data2.get("venta", 0.0))
            if compra > 0 and venta > 0:
                return round(compra, 2), round(venta, 2)
    except Exception as e:
        logging.error(f"Error en Fuente 2: {e}")

    return 0.0, 0.0

def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot Binance P2P activos*\n\n"
        "Envía `/status` para consultar los precios actualizados.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P...")
        
        sell_p, buy_p = get_p2p_price()

        if sell_p > 0 and buy_p > 0:
            hora_ve = get_venezuela_time()
            respuesta = (
                f"📊 *PRECIOS BINANCE P2P*\n"
                f"──────────────────────────────\n"
                f"🟢 *Comprar USDT (Venta):* `{sell_p} VES`\n"
                f"🔴 *Vender USDT (Recompra):* `{buy_p} VES`\n"
                f"🏛️ *Método:* `Banco de Venezuela`\n"
                f"──────────────────────────────\n"
                f"⏰ *Hora Venezuela:* `{hora_ve}`"
            )
            await msg_wait.edit_text(respuesta, parse_mode="Markdown")
        else:
            await msg_wait.edit_text("❌ No se pudieron obtener los precios en este momento. Revisa los logs de Render.")
    except Exception as e:
        logging.error(f"Error en el comando status: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error inesperado al procesar la solicitud.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("No se encontró TELEGRAM_BOT_TOKEN.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    print("🚀 Bot iniciado correctamente...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
