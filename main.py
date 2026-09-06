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

# --- CONSULTA P2P BINANCE BANCO DE VENEZUELA ---
def get_p2p_price():
    # Usamos una API abierta directa conectada a Binance P2P VES
    url = "https://ve.dolarapi.com/v1/dolares/oficial" # Endpoint de respaldo ligero
    url_binance = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar/unit/binance"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    try:
        # Intentamos obtener la tasa exacta de Binance
        res = requests.get(url_binance, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            price = float(data.get("price", 0.0))
            if price > 0:
                return price
    except Exception as e:
        logging.error(f"Error en endpoint primario: {e}")

    # Método de respaldo secundario directo
    try:
        res_backup = requests.get("https://monitordolarvenezuela.com/api/v1/dollar", headers=headers, timeout=10)
        if res_backup.status_code == 200:
            data_b = res_backup.json()
            # Buscar el monitor de Binance
            for item in data_b.get("monitors", []):
                if "binance" in item.get("key", "").lower():
                    return float(item.get("price", 0.0))
    except Exception as e:
        logging.error(f"Error en endpoint de respaldo: {e}")

    return 0.0

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Banco de Venezuela)*\n\n"
        "Envía el comando `/status` para obtener la tasa P2P en tiempo real.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando tasa en tiempo real...")
    
    price = get_p2p_price()

    if price > 0:
        respuesta = (
            f"📊 *TASA BINANCE P2P (VES)*\n"
            f"──────────────────────────────\n"
            f"💵 *Precio USDT:* `{price} VES`\n"
            f"🏛️ *Método:* `Banco de Venezuela`\n"
            f"──────────────────────────────\n"
            f"⏰ *Actualizado:* `{datetime.now().strftime('%I:%M:%S %p')}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text(
            "⚠️ *Servidor de Binance no respondió.*\n"
            "Por favor, intenta enviar `/status` nuevamente en 10 segundos.",
            parse_mode="Markdown"
        )

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
