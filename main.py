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

# --- OBTENER PRECIOS P2P (COMPRA Y VENTA) ---
def get_p2p_price():
    """
    Obtiene los precios de Venta (Comprar USDT) y Compra (Vender USDT)
    usando el endpoint P2P para Binance VES.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        # Petición a CriptoYa (Devuelve libro de ordenes Binance P2P VES)
        res_sell = requests.get("https://criptoya.com/api/binancep2p/sell/usdt/ves/5", headers=headers, timeout=6)
        res_buy = requests.get("https://criptoya.com/api/binancep2p/buy/usdt/ves/5", headers=headers, timeout=6)
        
        sell_price = 0.0
        buy_price = 0.0

        if res_sell.status_code == 200:
            data_sell = res_sell.json()
            if isinstance(data_sell, list) and len(data_sell) > 0:
                sell_price = float(data_sell[0].get("price", 0.0))

        if res_buy.status_code == 200:
            data_buy = res_buy.json()
            if isinstance(data_buy, list) and len(data_buy) > 0:
                buy_price = float(data_buy[0].get("price", 0.0))

        return round(sell_price, 2), round(buy_price, 2)

    except Exception as e:
        logging.error(f"Error consultando precios P2P: {e}")
        return 0.0, 0.0

# --- HORA LOCAL DE VENEZUELA (UTC-4) ---
def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Banco de Venezuela)*\n\n"
        "Envía el comando `/status` para obtener los precios actualizados de compra y venta.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P...")
    
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
            f"🏛️ *Método:* `Banco de Venezuela / General`\n"
            f"──────────────────────────────\n"
            f"⏰ *Hora Venezuela:* `{hora_ve}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se pudieron obtener los precios P2P en este momento. Intenta de nuevo.")

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
