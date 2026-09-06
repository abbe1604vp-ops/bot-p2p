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

# --- OBTENER PRECIOS P2P BINANCE (BANCO DE VENEZUELA) ---
def get_p2p_price():
    """
    Consulta Binance P2P directamente con headers de navegador.
    Si falla, utiliza la API de PyDolarVenezuela como respaldo.
    """
    url_binance = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    
    headers = {
        "Accept": "*/*",
        "Accept-Language": "es-ES,es;q=0.9",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    # 1. Intentar consulta directa a Binance P2P (Banco de Venezuela)
    try:
        # Tasa Venta (Comprar USDT con Banco de Venezuela)
        payload_sell = {
            "asset": "USDT",
            "fiat": "VES",
            "tradeType": "BUY",
            "page": 1,
            "rows": 5,
            "payTypes": ["BANK_OF_VENEZUELA"]
        }
        # Tasa Recompra (Vender USDT con Banco de Venezuela)
        payload_buy = {
            "asset": "USDT",
            "fiat": "VES",
            "tradeType": "SELL",
            "page": 1,
            "rows": 5,
            "payTypes": ["BANK_OF_VENEZUELA"]
        }

        res_sell = requests.post(url_binance, json=payload_sell, headers=headers, timeout=6)
        res_buy = requests.post(url_binance, json=payload_buy, headers=headers, timeout=6)

        sell_p = 0.0
        buy_p = 0.0

        if res_sell.status_code == 200:
            data_s = res_sell.json()
            if data_s.get("data"):
                sell_p = float(data_s["data"][0]["adv"]["price"])

        if res_buy.status_code == 200:
            data_b = res_buy.json()
            if data_b.get("data"):
                buy_p = float(data_b["data"][0]["adv"]["price"])

        if sell_p > 0 and buy_p > 0:
            return round(sell_p, 2), round(buy_p, 2)

    except Exception as e:
        logging.error(f"Error consultando Binance directo: {e}")

    # 2. Respaldo: API PyDolarVenezuela
    try:
        url_respaldo = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=binance"
        res_resp = requests.get(url_respaldo, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        
        if res_resp.status_code == 200:
            data_r = res_resp.json()
            base_price = float(data_r.get("price", 0.0))
            if base_price > 0:
                # Estimación de spread estándar si el respaldo devuelve tasa promedio
                return round(base_price * 1.005, 2), round(base_price * 0.995, 2)

    except Exception as e:
        logging.error(f"Error consultando API de respaldo: {e}")

    return 0.0, 0.0

# --- HORA LOCAL DE VENEZUELA (UTC-4) ---
def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Banco de Venezuela)*\n\n"
        "Envía `/status` para consultar los precios actualizados de compra y venta.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P (Banco de Venezuela)...")
    
    sell_p, buy_p = get_p2p_price()

    if sell_p > 0 and buy_p > 0:
        spread = round(sell_p - buy_p, 2)
        hora_ve = get_venezuela_time()
        
        respuesta = (
            f"📊 *PRECIOS P2P BINANCE (VES)*\n"
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
        await msg_wait.edit_text("❌ No se pudieron obtener las tasas en este momento. Intenta de nuevo en unos segundos.")

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
