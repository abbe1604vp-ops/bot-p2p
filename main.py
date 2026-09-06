import asyncio
import logging
import requests
import csv
from datetime import datetime, timezone, timedelta
from collections import deque
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURACIÓN ---
TELEGRAM_BOT_TOKEN = "6327813571:AAGcRK1xNEVy9xqC2SHqQxZiK7I1sOzq89I"
CHAT_ID_NOTIFICACIONES = None

FIAT = "VES"
ASSET = "USDT"
COMMISSION_PERCENT = 0.35
MIN_SPREAD_ALERT = 1.0

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
CSV_FILE = "historial_p2p.csv"

# Zona horaria Venezuela (UTC-4)
VET = timezone(timedelta(hours=-4))

# Memoria temporal (hasta 720 lecturas = 24h)
PRICE_HISTORY = deque(maxlen=720)

logging.basicConfig(level=logging.INFO)

# Crear archivo CSV con encabezados si no existe
try:
    with open(CSV_FILE, mode='x', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Fecha_Hora", "Compra_VES", "Venta_VES", "Spread_Neto"])
except FileExistsError:
    pass

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

def get_market_bias():
    """Calcula el sesgo y comportamiento del mercado basado en fluctuaciones recientes."""
    if len(PRICE_HISTORY) < 5:
        return "⏳ Analizando flujo de mercado..."

    recent_sells = [p["sell"] for p in list(PRICE_HISTORY)[-10:]]
    diff_pct = ((recent_sells[-1] - recent_sells[0]) / recent_sells[0]) * 100

    if diff_pct >= 0.3:
        return "🚀 ALCISTA FUERTE (Presión al alza)"
    elif diff_pct >= 0.1:
        return "↗️ LATERAL CON SESGO ALCISTA"
    elif diff_pct <= -0.3:
        return "📉 BAJISTA ACELERADO (Corrección activa)"
    elif diff_pct <= -0.1:
        return "↘️ LATERAL CON SESGO BAJISTA"
    else:
        return "➡️ LATERAL ESTABLE (En rango)"

def get_market_signals(current_buy, current_sell):
    if len(PRICE_HISTORY) < 5:
        return None

    sells = [p["sell"] for p in PRICE_HISTORY]
    buys = [p["buy"] for p in PRICE_HISTORY]

    max_sell = max(sells)
    min_buy = min(buys)

    signal = "NEUTRAL"
    if current_sell >= max_sell * 0.999:
        signal = "PUNTO_VENTA_OPTIMO"
    elif current_buy <= min_buy * 1.001:
        signal = "PUNTO_RECOMPRA_OPTIMO"

    return {
        "max_sell": max_sell,
        "min_buy": min_buy,
        "signal": signal
    }

def save_to_history(data):
    now_vet = datetime.now(VET)
    timestamp_str = now_vet.strftime("%Y-%m-%d %H:%M:%S")

    PRICE_HISTORY.append({
        "time": now_vet,
        "buy": data["buy"],
        "sell": data["sell"],
        "spread_net": data["spread_net"]
    })

    try:
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                int(now_vet.timestamp()),
                timestamp_str,
                data["buy"],
                data["sell"],
                f"{data['spread_net']:.2f}"
            ])
    except Exception as e:
        logging.error(f"Error guardando CSV: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_NOTIFICACIONES
    CHAT_ID_NOTIFICACIONES = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 *ARBITRAJE PRO — BOT ACTIVO*\n\n"
        f"Par: *{ASSET}/{FIAT}*\n"
        f"Motor analítico estilo ArBit inicializado.\n\n"
        f"📋 *Comandos Principales:*\n"
        f"• /status — Panel general del mercado\n"
        f"• /senales — Puntos óptimos y sesgo actual\n"
        f"• /historial — Registro de lecturas activas",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = calculate_arbitrage()
    if not res:
        await update.message.reply_text("⚠️ Error al conectar con Binance P2P.")
        return

    bias = get_market_bias()
    signals = get_market_signals(res["buy"], res["sell"])
    
    max_s = signals['max_sell'] if signals else res['sell']
    min_b = signals['min_buy'] if signals else res['buy']

    msg = (
        f"📊 *PANEL DE MERCADO P2P ({ASSET}/{FIAT})*\n"
        f"──────────────────────────────\n"
        f"🔴 *Venta (P2P):* `{res['sell']:.2f} {FIAT}`\n"
        f"🟢 *Compra (P2P):* `{res['buy']:.2f} {FIAT}`\n\n"
        f"📈 *Spread Bruto:* `{res['spread_gross']:.2f}%`\n"
        f"💵 *Margen Neto:* `{res['spread_net']:.2f}%`\n"
        f"──────────────────────────────\n"
        f"📌 *Sesgo Actual:* {bias}\n"
        f"🔝 *Máximo del día:* `{max_s:.2f} {FIAT}`\n"
        f"🔻 *Mínimo del día:* `{min_b:.2f} {FIAT}`\n"
        f"📁 *Registros:* `{len(PRICE_HISTORY)} lecturas`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def senales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = calculate_arbitrage()
    if not res:
        await update.message.reply_text("⚠️ Error al procesar precios.")
        return

    signals = get_market_signals(res["buy"], res["sell"])
    bias = get_market_bias()
    
    if not signals:
        await update.message.reply_text("⏳ Recopilando datos de tendencia (espera unos minutos)...")
        return

    sig_header = "🔍 *ANÁLISIS TÉCNICO Y SEÑALES*"
    action_rec = "Mantener posición / Monitorear"
    
    if signals["signal"] == "PUNTO_VENTA_OPTIMO":
        sig_header = "🔴 *PUNTO DE VENTA ÓPTIMO — Confirmado*"
        action_rec = "¡VENDER AHORA (Zona de resistencia)!"
    elif signals["signal"] == "PUNTO_RECOMPRA_OPTIMO":
        sig_header = "🟢 *PUNTO DE RECOMPRA ÓPTIMO — Confirmado*"
        action_rec = "¡RECOMPRAR AHORA (Zona de soporte)!"

    msg = (
        f"{sig_header}\n"
        f"──────────────────────────────\n"
        f"🎯 *Recomendación:* `{action_rec}`\n\n"
        f"📉 *Comportamiento:* {bias}\n"
        f"🔹 *Precio Actual Venta:* `{res['sell']:.2f} {FIAT}`\n"
        f"🔹 *Precio Actual Compra:* `{res['buy']:.2f} {FIAT}`\n\n"
        f"📊 *Spread Ejecutable:* `{res['spread_net']:.2f}%`\n"
        f"⏰ *Hora Local VET:* `{datetime.now(VET).strftime('%I:%M %p')}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not PRICE_HISTORY:
        await update.message.reply_text("Aún no hay historial suficiente.")
        return
        
    p_ini = PRICE_HISTORY[0]['time'].strftime("%I:%M %p")
    p_fin = PRICE_HISTORY[-1]['time'].strftime("%I:%M %p")
    
    msg = (
        f"📁 *ESTADÍSTICAS DE HISTORIAL*\n"
        f"──────────────────────────────\n"
        f"• *Total Lecturas:* `{len(PRICE_HISTORY)}`\n"
        f"• *Rango de Tiempo:* `{p_ini} - {p_fin}`\n"
        f"• *Archivo:* `historial_p2p.csv` (Activo)"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def monitor_market(app: Application):
    last_signal_sent = None

    while True:
        res = calculate_arbitrage()
        if res:
            save_to_history(res)
            signals = get_market_signals(res["buy"], res["sell"])
            bias = get_market_bias()

            if CHAT_ID_NOTIFICACIONES and signals:
                sig_type = signals["signal"]
                
                if sig_type in ["PUNTO_VENTA_OPTIMO", "PUNTO_RECOMPRA_OPTIMO"] and sig_type != last_signal_sent:
                    last_signal_sent = sig_type
                    
                    emoji_sig = "🔴" if sig_type == "PUNTO_VENTA_OPTIMO" else "🟢"
                    action_txt = "¡VENDER AHORA!" if sig_type == "PUNTO_VENTA_OPTIMO" else "¡RECOMPRAR AHORA!"
                    
                    alert_msg = (
                        f"{emoji_sig} *ALERTA DE OPORTUNIDAD P2P*\n"
                        f"──────────────────────────────\n"
                        f"👉 *Acción:* `{action_txt}`\n"
                        f"📌 *Sesgo:* {bias}\n\n"
                        f"📍 *Venta:* `{res['sell']:.2f} {FIAT}`\n"
                        f"📍 *Compra:* `{res['buy']:.2f} {FIAT}`\n"
                        f"🔝 *Máximo:* `{signals['max_sell']:.2f} {FIAT}`\n\n"
                        f"⚡ *Spread Neto:* `{res['spread_net']:.2f}%`"
                    )
                    await app.bot.send_message(
                        chat_id=CHAT_ID_NOTIFICACIONES, 
                        text=alert_msg, 
                        parse_mode="Markdown"
                    )

        await asyncio.sleep(120)

async def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("senales", senales))
    app.add_handler(CommandHandler("historial", historial))

    asyncio.create_task(monitor_market(app))

    print("Bot con formato visual avanzado y sesgo activo...")
    
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
