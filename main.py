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

# --- CONSULTA ROBUSTA DE DÓLAR P2P / PARALELO VENEZUELA ---
def get_p2p_price():
    """Consulta múltiples fuentes abiertas optimizadas para servidores Cloud."""
    
    # Fuente 1: DolarApi (P2P / Paralelo)
    try:
        res = requests.get("https://ve.dolarapi.com/v1/dolares/paralelo", timeout=5)
        if res.status_code == 200:
            data = res.json()
            precio = float(data.get("promedio", 0.0))
            if precio > 0:
                return precio
    except Exception as e:
        logging.error(f"Error en DolarApi Paralelo: {e}")

    # Fuente 2: CriptoYa (Binance P2P VES directo por API pública autorizada)
    try:
        res = requests.get("https://criptoya.com/api/binancep2p/sell/usdt/ves/5", timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                precio = float(data[0].get("price", 0.0))
                if precio > 0:
                    return precio
    except Exception as e:
        logging.error(f"Error en CriptoYa P2P: {e}")

    # Fuente 3: Exchangerate API Respaldo
    try:
        res = requests.get("https://ve.dolarapi.com/v1/dolares", timeout=5)
        if res.status_code == 200:
            data = res.json()
            for item in data:
                if item.get("fuente") == "paralelo":
                    return float(item.get("promedio", 0.0))
    except Exception as e:
        logging.error(f"Error en DolarApi Lista: {e}")

    return 0.0

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance / Mercado Venezuela*\n\n"
        "Envía el comando `/status` para obtener la tasa en tiempo real.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando tasa de cambio...")
    
    price = get_p2p_price()

    if price > 0:
        respuesta = (
            f"📊 *TASA DE CAMBIO P2P / MERCADO (VES)*\n"
            f"──────────────────────────────\n"
            f"💵 *Precio USDT:* `{price} VES`\n"
            f"🏛️ *Método:* `Banco de Venezuela / P2P`\n"
            f"──────────────────────────────\n"
            f"⏰ *Actualizado:* `{datetime.now().strftime('%I:%M:%S %p')}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se pudo conectar con los servidores de tasa. Intenta en un momento.")

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
