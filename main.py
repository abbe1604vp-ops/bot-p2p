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

def get_binance_p2p_price_direct(trade_type: str):
    """
    Obtiene la primera oferta activa en Binance P2P para Banco de Venezuela.
    trade_type: 'BUY' para Venta (Comprar USDT), 'SELL' para Recompra (Vender USDT)
    """
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "es-ES,es;q=0.9",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "Origin": "https://p2p.binance.com",
        "Pragma": "no-cache",
        "Referer": "https://p2p.binance.com/es/trade/all-payments/USDT?fiat=VES",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    payload = {
        "asset": "USDT",
        "fiat": "VES",
        "merchantCheck": False,
        "page": 1,
        "payTypes": ["BANK_OF_VENEZUELA"],
        "publisherType": None,
        "rows": 5,
        "tradeType": trade_type
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and len(data["data"]) > 0:
                price = float(data["data"][0]["adv"]["price"])
                return price
    except Exception as e:
        logging.error(f"Error consultando Binance P2P ({trade_type}): {e}")
        
    return 0.0

def get_p2p_price():
    # BUY = Anuncios de usuarios vendiendo USDT (lo que tú pagas para comprar)
    sell_price = get_binance_p2p_price_direct("BUY")
    # SELL = Anuncios de usuarios comprando USDT (lo que te pagan al vender)
    buy_price = get_binance_p2p_price_direct("SELL")

    # Si Binance responde directo, devolvemos los precios reales
    if sell_price > 0 and buy_price > 0:
        return round(sell_price, 2), round(buy_price, 2)

    # Respaldo rápido vía PyDolarVenezuela filtrado si hay micro-bloqueos
    try:
        res = requests.get("https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=binance", timeout=5)
        if res.status_code == 200:
            p = float(res.json().get("price", 0.0))
            if p > 0:
                return round(p, 2), round(p, 2)
    except Exception:
        pass

    return 0.0, 0.0

def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot P2P Binance (Banco de Venezuela)*\n\n"
        "Envía `/status` para consultar la tasa oficial exacta.",
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
