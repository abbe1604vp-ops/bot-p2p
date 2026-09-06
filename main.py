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
    Consulta los precios exactos de Binance P2P (Banco de Venezuela)
    usando agregadores de datos P2P que no bloquean las IPs de Render.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Opción 1: API de VeDolar (Extracción P2P Binance real en tiempo real)
    try:
        url = "https://api.vedolar.com/v1/binance/p2p?fiat=VES&payType=BANK_OF_VENEZUELA"
        res = requests.get(url, headers=headers, timeout=7)
        if res.status_code == 200:
            data = res.json()
            sell_p = float(data.get("buy", 0.0))   # Lo que cuesta comprar USDT
            buy_p = float(data.get("sell", 0.0))    # Lo que pagan por vender USDT
            if sell_p > 0 and buy_p > 0:
                return round(sell_p, 2), round(buy_p, 2)
    except Exception as e:
        logging.error(f"Error Opción 1: {e}")

    # Opción 2: Respaldo con CriptoYa con formateo explícito de headers
    try:
        url_sell = "https://criptoya.com/api/binancep2p/sell/usdt/ves/1"
        url_buy = "https://criptoya.com/api/binancep2p/buy/usdt/ves/1"
        
        r_sell = requests.get(url_sell, headers=headers, timeout=6)
        r_buy = requests.get(url_buy, headers=headers, timeout=6)

        if r_sell.status_code == 200 and r_buy.status_code == 200:
            d_sell = r_sell.json()
            d_buy = r_buy.json()
            
            # CriptoYa devuelve una lista con las mejores órdenes
            if isinstance(d_sell, list) and len(d_sell) > 0 and isinstance(d_buy, list) and len(d_buy) > 0:
                price_sell = float(d_sell[0].get("price", 0.0))
                price_buy = float(d_buy[0].get("price", 0.0))
                if price_sell > 0 and price_buy > 0:
                    return round(price_sell, 2), round(price_buy, 2)
    except Exception as e:
        logging.error(f"Error Opción 2: {e}")

    # Opción 3: DolarApi como respaldo final
    try:
        res = requests.get("https://ve.dolarapi.com/v1/dolares/p2p/binance", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            compra = float(data.get("compra", 0.0))
            venta = float(data.get("venta", 0.0))
            if compra > 0 and venta > 0:
                return round(compra, 2), round(venta, 2)
    except Exception as e:
        logging.error(f"Error Opción 3: {e}")

    return 0.0, 0.0

def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Banco de Venezuela)*\n\n"
        "Envía `/status` para consultar la tasa P2P en tiempo real.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P (Banco de Venezuela)...")
    
    sell_p, buy_p = get_p2p_price()

    if sell_p > 0 and buy_p > 0:
        spread = round(abs(sell_p - buy_p), 2)
        hora_ve = get_venezuela_time()
        
        respuesta = (
            f"📊 *PRECIOS REALES BINANCE P2P*\n"
            f"──────────────────────────────\n"
            f"🟢 *Comprar USDT (Venta):* `{sell_p} VES`\n"
            f"🔴 *Vender USDT (Recompra):* `{buy_p} VES`\n"
            f"📐 *Spread:* `{spread} VES`\n"
            f"🏛️ *Método:* `Banco de Venezuela`\n"
            f"──────────────────────────────\n"
            f"⏰ *Hora Venezuela:* `{hora_ve}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se pudieron obtener los precios en este momento. Intenta de nuevo en unos segundos.")

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
