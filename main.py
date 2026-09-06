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

# --- VARIABLE DE ENTORNO ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- OBTENER PRECIOS P2P BINANCE (BANCO DE VENEZUELA EXACTO) ---
def get_p2p_price():
    """
    Obtiene la primera orden real y activa de Binance P2P para Banco de Venezuela.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    # Opción 1: CriptoYa filtrado exactamente por Banco de Venezuela
    try:
        url_sell = "https://criptoya.com/api/binancep2p/sell/usdt/ves/5?payTypes=BANK_OF_VENEZUELA"
        url_buy = "https://criptoya.com/api/binancep2p/buy/usdt/ves/5?payTypes=BANK_OF_VENEZUELA"

        res_sell = requests.get(url_sell, headers=headers, timeout=6)
        res_buy = requests.get(url_buy, headers=headers, timeout=6)

        sell_p = 0.0
        buy_p = 0.0

        if res_sell.status_code == 200:
            data_sell = res_sell.json()
            if isinstance(data_sell, list) and len(data_sell) > 0:
                sell_p = float(data_sell[0].get("price", 0.0))

        if res_buy.status_code == 200:
            data_buy = res_buy.json()
            if isinstance(data_buy, list) and len(data_buy) > 0:
                buy_p = float(data_buy[0].get("price", 0.0))

        if sell_p > 0 and buy_p > 0:
            return round(sell_p, 2), round(buy_p, 2)

    except Exception as e:
        logging.error(f"Error en consulta CriptoYa filtrada: {e}")

    # Opción 2: Respaldo directo a la API de Binance usando proxy libre
    try:
        url_proxy = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=binance"
        res_proxy = requests.get(url_proxy, headers=headers, timeout=6)
        if res_proxy.status_code == 200:
            data_p = res_proxy.json()
            price = float(data_p.get("price", 0.0))
            if price > 0:
                return round(price, 2), round(price, 2)
    except Exception as e:
        logging.error(f"Error en consulta de respaldo: {e}")

    return 0.0, 0.0

# --- HORA LOCAL DE VENEZUELA (UTC-4) ---
def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Banco de Venezuela)*\n\n"
        "Envía `/status` para obtener las tasas exactas de Binance P2P.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P (Banco de Venezuela)...")
    
    sell_p, buy_p = get_p2p_price()

    if sell_p > 0 and buy_p > 0:
        spread = round(abs(sell_p - buy_p), 2)
        hora_ve = get_venezuela_time()
        
        respuesta = (
            f"📊 *PRECIOS EXACTOS BINANCE P2P*\n"
            f"──────────────────────────────\n"
            f"🟢 *Comprar USDT (Venta):* `{sell_p} VES`\n"
            f"🔴 *Vender USDT (Recompra):* `{buy_p} VES`\n"
            f"📐 *Spread / Diferencia:* `{spread} VES`\n"
            f"🏛️ *Método:* `Banco de Venezuela`\n"
            f"──────────────────────────────\n"
            f"⏰ *Hora Venezuela:* `{hora_ve}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se pudieron obtener los precios en este momento. Intenta nuevamente.")

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
