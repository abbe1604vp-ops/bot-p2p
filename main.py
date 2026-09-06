import os
import logging
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Variable global para guardar los usuarios que recibirán alertas
USER_CHAT_IDS = set()

def get_p2p_price():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    # Fuente 1: CriptoYa Binance P2P VES
    try:
        url = "https://criptoya.com/api/binancep2p/usdt/ves/1"
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            ask = float(data.get("ask", 0.0))  # Comprar USDT
            bid = float(data.get("bid", 0.0))  # Vender USDT
            if ask > 0 and bid > 0:
                return round(ask, 2), round(bid, 2)
    except Exception as e:
        logging.error(f"Error Fuente 1 CriptoYa: {e}")

    # Fuente 2: DolarApi (Respaldo)
    try:
        url2 = "https://ve.dolarapi.com/v1/dolares/p2p/binance"
        res2 = requests.get(url2, headers=headers, timeout=8)
        if res2.status_code == 200:
            data2 = res2.json()
            compra = float(data2.get("compra", 0.0))
            venta = float(data2.get("venta", 0.0))
            if compra > 0 and venta > 0:
                return round(venta, 2), round(compra, 2)
    except Exception as e:
        logging.error(f"Error Fuente 2 DolarApi: {e}")

    return 0.0, 0.0

def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve).strftime("%I:%M:%S %p")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    USER_CHAT_IDS.add(chat_id)
    
    await update.message.reply_text(
        "🤖 *Bot Binance P2P Activo y Monitoreando*\n\n"
        "✅ Te enviaré una *ALERTA AUTOMÁTICA* cuando la diferencia (spread) entre compra y venta sea de 10 VES o más.\n\n"
        "Envía `/status` en cualquier momento para ver los precios actuales.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Guardar el chat id para asegurar que reciba alertas
    USER_CHAT_IDS.add(update.effective_chat.id)
    
    try:
        msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P...")
        sell_p, buy_p = get_p2p_price()

        if sell_p > 0 and buy_p > 0:
            spread_ves = round(abs(sell_p - buy_p), 2)
            spread_porcentaje = round((spread_ves / sell_p) * 100, 2)
            hora_ve = get_venezuela_time()
            
            respuesta = (
                f"📊 *PRECIOS BINANCE P2P*\n"
                f"──────────────────────────────\n"
                f"🟢 *Comprar USDT (Venta):* `{sell_p} VES`\n"
                f"🔴 *Vender USDT (Recompra):* `{buy_p} VES`\n"
                f"──────────────────────────────\n"
                f"📐 *Spread:* `{spread_ves} VES` (`{spread_porcentaje}%`)\n"
                f"🏛️ *Método:* `Banco de Venezuela / P2P`\n"
                f"──────────────────────────────\n"
                f"⏰ *Hora Venezuela:* `{hora_ve}`"
            )
            await msg_wait.edit_text(respuesta, parse_mode="Markdown")
        else:
            await msg_wait.edit_text("❌ Servidores ocupados. Intenta de nuevo en unos segundos.")
    except Exception as e:
        logging.error(f"Error en comando status: {e}")

# Tarea automática en segundo plano
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not USER_CHAT_IDS:
        return

    sell_p, buy_p = get_p2p_price()
    if sell_p > 0 and buy_p > 0:
        spread_ves = round(abs(sell_p - buy_p), 2)
        
        # ALERTA: Si la diferencia es de 10 puntos/VES o más
        if spread_ves >= 10.0:
            hora_ve = get_venezuela_time()
            spread_porcentaje = round((spread_ves / sell_p) * 100, 2)
            
            alerta_msg = (
                f"🚨 *¡ALERTA OPORTUNA DE SPREAD!* 🚨\n\n"
                f"El diferencial superó los 10 VES:\n"
                f"📐 *Spread Actual:* `{spread_ves} VES` (`{spread_porcentaje}%`)\n\n"
                f"🟢 *Comprar USDT:* `{sell_p} VES`\n"
                f"🔴 *Vender USDT:* `{buy_p} VES`\n"
                f"⏰ *Hora:* `{hora_ve}`\n\n"
                f"⚡ *Oportunidad de arbitraje / operación detectada.*"
            )
            
            for chat_id in USER_CHAT_IDS:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=alerta_msg, parse_mode="Markdown")
                except Exception as e:
                    logging.error(f"Error enviando alerta a {chat_id}: {e}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("No se encontró TELEGRAM_BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    # Tarea en segundo plano: Ejecuta 'check_alerts' cada 60 segundos
    if app.job_queue:
        app.job_queue.run_repeating(check_alerts, interval=60, first=10)

    print("🚀 Bot con alertas automáticas iniciado...")
    app.run_polling()

if __name__ == "__main__":
    main()
