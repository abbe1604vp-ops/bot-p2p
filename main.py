import os
import logging
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def get_p2p_price():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    # Fuente 1: API Directa CriptoYa Binance P2P VES
    try:
        url = "https://criptoya.com/api/binancep2p/usdt/ves/1"
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            ask = float(data.get("ask", 0.0))  # Precio Venta / Comprar
            bid = float(data.get("bid", 0.0))  # Precio Recompra / Vender
            if ask > 0 and bid > 0:
                return round(ask, 2), round(bid, 2)
    except Exception as e:
        logging.error(f"Error Fuente 1 CriptoYa: {e}")

    # Fuente 2: DolarApi Venezuela
    try:
        url2 = "https://ve.dolarapi.com/v1/dolares/p2p/binance"
        res2 = requests.get(url2, headers=headers, timeout=8)
        if res2.status_code == 200:
            data2 = res2.json()
            compra = float(data2.get("promedio", data2.get("compra", 0.0)))
            if compra > 0:
                return round(compra, 2), round(compra, 2)
    except Exception as e:
        logging.error(f"Error Fuente 2 DolarApi: {e}")

    # Fuente 3: Exchangerate API (Respaldo final)
    try:
        url3 = "https://open.er-api.com/v6/latest/USD"
        res3 = requests.get(url3, headers=headers, timeout=8)
        if res3.status_code == 200:
            rates = res3.json().get("rates", {})
            ves = float(rates.get("VES", 0.0))
            if ves > 0:
                return round(ves, 2), round(ves, 2)
    except Exception as e:
        logging.error(f"Error Fuente 3 OpenER: {e}")

    return 0.0, 0.0

def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot Binance P2P activo*\n\n"
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
                f"🏛️ *Método:* `Banco de Venezuela / P2P`\n"
                f"──────────────────────────────\n"
                f"⏰ *Hora Venezuela:* `{hora_ve}`"
            )
            await msg_wait.edit_text(respuesta, parse_mode="Markdown")
        else:
            await msg_wait.edit_text("❌ Servidores de consulta ocupados. Intenta de nuevo en unos segundos.")
    except Exception as e:
        logging.error(f"Error en el comando status: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al procesar la orden.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("No se encontró TELEGRAM_BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    print("🚀 Bot iniciado correctamente...")
    app.run_polling()

if __name__ == "__main__":
    main()
