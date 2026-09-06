import asyncio
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURACIÓN ---
TELEGRAM_BOT_TOKEN = "6327813571:AAGG9YW2iaKW9A7tsDzXTi3ka5-uaThkQd0"
CHAT_ID_NOTIFICACIONES = None

FIAT = "VES"            # Moneda local (VES para Bolívares)
ASSET = "USDT"          # Criptomoneda
COMMISSION_PERCENT = 0.35 # Comisión estimada (%)
MIN_SPREAD_ALERT = 1.0  # Margen mínimo de ganancia (%) para alerta

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

logging.basicConfig(level=logging.INFO)

def get_p2p_price(trade_type: str, fiat: str, asset: str) -> float:
    payload = {
        "fiat": fiat,
        "page": 1,
        "rows": 5,
        "tradeType": trade_type,
        "asset": asset,
        "countries": [],
        "proMerchantAds": False,
        "shieldMerchantAds": False,
        "publisherType": None
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(BINANCE_P2P_URL, json=payload, headers=headers, timeout=10)
        data = response.json()
        if data.get("success") and data.get("data"):
            return float(data["data"][0]["adv"]["price"])
    except Exception as e:
        logging.error(f"Error Binance P2P ({trade_type}): {e}")
    return 0.0

def calculate_arbitrage():
    price_buy = get_p2p_price("BUY", FIAT, ASSET)
    price_sell = get_p2p_price("SELL", FIAT, ASSET)

    if price_buy == 0 or price_sell == 0:
        return None

    spread_gross = ((price_sell - price_buy) / price_buy) * 100
    spread_net = spread_gross - (COMMISSION_PERCENT * 2)

    return {
        "buy": price_buy,
        "sell": price_sell,
        "spread_gross": spread_gross,
        "spread_net": spread_net
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_NOTIFICACIONES
    CHAT_ID_NOTIFICACIONES = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 Bot de Arbitraje P2P Activado\n\n"
        f"Monitoreando: {ASSET}/{FIAT}\n"
        f"Alerta cuando el spread supere el {MIN_SPREAD_ALERT}%.\n\n"
        f"Comando disponible: /status"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = calculate_arbitrage()
    if not res:
        await update.message.reply_text("⚠️ Error al obtener precios de Binance P2P.")
        return

    msg = (
        f"📊 Binance P2P ({ASSET}/{FIAT})\n\n"
        f"🔴 Compra: {res['buy']:.2f} {FIAT}\n"
        f"🟢 Venta: {res['sell']:.2f} {FIAT}\n\n"
        f"📈 Spread Bruto: {res['spread_gross']:.2f}%\n"
        f"💵 Margen Neto: {res['spread_net']:.2f}%"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def monitor_market(app: Application):
    while True:
        await asyncio.sleep(15)
        if CHAT_ID_NOTIFICACIONES:
            res = calculate_arbitrage()
            if res and res["spread_net"] >= MIN_SPREAD_ALERT:
                alert_msg = (
                    f"🚀 ¡OPORTUNIDAD DE ARBITRAJE!\n\n"
                    f"🔹 Comprar: {res['buy']:.2f} {FIAT}\n"
                    f"🔹 Vender: {res['sell']:.2f} {FIAT}\n\n"
                    f"⚡ Spread Neto: {res['spread_net']:.2f}%"
                )
                await app.bot.send_message(
                    chat_id=CHAT_ID_NOTIFICACIONES, 
                    text=alert_msg, 
                    parse_mode="Markdown"
                )
                await asyncio.sleep(120)

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    loop = asyncio.get_event_loop()
    loop.create_task(monitor_market(app))

    print("Bot corriendo correctamente...")
    app.run_polling()

if __name__ == "__main__":
    main()
