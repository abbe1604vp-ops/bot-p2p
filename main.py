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

# --- OBTENER TASAS DE BINANCE VENEZUELA (VÍA YADIO API) ---
def get_p2p_price():
    url = "https://api.yadio.io/exchanges"
    try:
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            data = response.json()
            binance_data = data.get("Binance", {}).get("VES", {})
            
            sell_price = float(binance_data.get("sell", 0.0))  # Precio Venta USDT
            buy_price = float(binance_data.get("buy", 0.0))    # Precio Compra USDT
            
            return round(sell_price, 2), round(buy_price, 2)
    except Exception as e:
        logging.error(f"Error consultando API alternativa: {e}")
    
    return 0.0, 0.0

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Venezuela)*\n\n"
        "Envía el comando `/status` para obtener los precios actualizados.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P...")
    
    sell_p, buy_p = get_p2p_price()

    if sell_p > 0 and buy_p > 0:
        spread = round(sell_p - buy_p, 2)
        
        respuesta = (
            f"📊 *PRECIOS BINANCE P2P (VES)*\n"
            f"──────────────────────────────\n"
            f"🟢 *Comprar USDT (Venta):* `{sell_p} VES`\n"
            f"🔴 *Vender USDT (Recompra):* `{buy_p} VES`\n"
            f"📐 *Spread / Diferencia:* `{spread} VES`\n"
            f"──────────────────────────────\n"
            f"⏰ *Hora:* `{datetime.now().strftime('%I:%M:%S %p')}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se pudieron obtener las tasas en este momento.")

# --- INICIALIZACIÓN ---
def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("No se encontró la variable de entorno TELEGRAM_BOT_TOKEN.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    print("🚀 Bot iniciado correctamente...")
    app.run_polling()

if __name__ == "__main__":
    main()
