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

# --- OBTENER PRECIOS P2P BINANCE ---
def get_p2p_price():
    """
    Obtiene los precios P2P de Binance (Compra y Venta)
    usando DolarApi, optimizada para servidores Cloud sin bloqueo.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    try:
        # Endpoint directo P2P Binance en DolarApi
        url = "https://ve.dolarapi.com/v1/dolares/p2p/binance"
        res = requests.get(url, headers=headers, timeout=8)

        if res.status_code == 200:
            data = res.json()
            sell_p = float(data.get("compra", 0.0))  # Precio para comprar USDT (Venta del anunciante)
            buy_p = float(data.get("venta", 0.0))   # Precio para vender USDT (Compra del anunciante)

            if sell_p > 0 and buy_p > 0:
                return round(sell_p, 2), round(buy_p, 2)

    except Exception as e:
        logging.error(f"Error consultando DolarApi Binance P2P: {e}")

    # Respaldos adicionales si falla la primera opción
    try:
        url_alt = "https://ve.dolarapi.com/v1/dolares/paralelo"
        res_alt = requests.get(url_alt, headers=headers, timeout=8)
        if res_alt.status_code == 200:
            data_alt = res_alt.json()
            promedio = float(data_alt.get("promedio", 0.0))
            if promedio > 0:
                return round(promedio * 1.005, 2), round(promedio * 0.995, 2)
    except Exception as e:
        logging.error(f"Error en endpoint de respaldo: {e}")

    return 0.0, 0.0

# --- HORA LOCAL DE VENEZUELA (UTC-4) ---
def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Venezuela)*\n\n"
        "Envía `/status` para consultar los precios de compra y venta en tiempo real.",
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
