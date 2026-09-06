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

# Memoria temporal para cálculos rápidos de tendencia (máximo 100 registros)
PRICE_HISTORY = deque(maxlen=100)

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

def calculate_trend():
    """Analiza la tendencia comparando la lectura actual con lecturas anteriores."""
    if len(PRICE_HISTORY) < 3:
        return "⏳ Analizando mercado (acumulando datos...)"

    first_sell = PRICE_HISTORY[0]["sell"]
    last_sell = PRICE_HISTORY[-1]["sell"]
    diff_pct = ((last_sell - first_sell) / first_sell) * 100

    if diff_pct >= 0.2:
        return f"🚀 ALCISTA / SUBIENDO (+{diff_pct:.2f}%)"
    elif diff_pct <= -0.2:
        return f"📉 BAJISTA / CAYENDO ({diff_pct:.2f}%)"
    else:
        return f"➡️ LATERAL / ESTABLE ({diff_pct:+.2f}%)"

def save_to_history(data):
    now_vet = datetime.now(VET)
    timestamp_str = now_vet.strftime("%Y-%m-%d %H:%M:%S")

    # Guardar en memoria activa
    PRICE_HISTORY.append({
        "time": now_vet,
        "buy": data["buy"],
        "sell": data["sell"],
        "spread_net": data["spread_net"]
    })

    # Guardar en archivo CSV
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
        f"🤖 **Bot de Arbitraje P2P Activado**\n\n"
        f"Monitoreando: **{ASSET}/{FIAT}**\n"
        f"Frecuencia de monitoreo y guardado histórico: **Cada 2 minutos**\n"
        f"Alerta activa cuando el spread supere: **{MIN_SPREAD_ALERT}%**\n\n"
        f"Comandos disponibles:\n"
        f"/status - Ver precio actual y tendencia\n"
        f"/historial - Muestra cantidad de lecturas registradas"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = calculate_arbitrage()
    if not res:
        await update.message.reply_text("⚠️ Error al obtener precios de Binance P2P.")
        return

    trend = calculate_trend()
    msg = (
        f"📊 **Binance P2P ({ASSET}/{FIAT})**\n\n"
        f"🔴 **Compra (P2P):** {res['buy']:.2f} {FIAT}\n"
        f"🟢 **Venta (P2P):** {res['sell']:.2f} {FIAT}\n\n"
        f"📈 **Spread Bruto:** {res['spread_gross']:.2f}%\n"
        f"💵 **Margen Neto:** {res['spread_net']:.2f}%\n\n"
        f"📊 **Tendencia actual:** {trend}\n"
        f"💾 **Registros guardados:** {len(PRICE_HISTORY)} lecturas"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not PRICE_HISTORY:
        await update.message.reply_text("Aún no hay suficiente historial acumulado.")
        return
        
    primer_registro = PRICE_HISTORY[0]['time'].strftime("%I:%M %p")
    ultimo_registro = PRICE_HISTORY[-1]['time'].strftime("%I:%M %p")
    
    msg = (
        f"📁 **Historial del Mercado (En memoria)**\n\n"
        f"🔹 **Lecturas almacenadas:** {len(PRICE_HISTORY)}\n"
        f"🔹 **Desde:** {primer_registro}\n"
        f"🔹 **Hasta:** {ultimo_registro}\n\n"
        f"El bot continúa registrando datos cada 2 minutos en el archivo `.csv`."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def monitor_market(app: Application):
    while True:
        res = calculate_arbitrage()
        if res:
            # Guardar histórico cada 2 minutos
            save_to_history(res)
            
            # Notificar si hay oportunidad de arbitraje
            if CHAT_ID_NOTIFICACIONES and res["spread_net"] >= MIN_SPREAD_ALERT:
                alert_msg = (
                    f"🚀 **¡OPORTUNIDAD DE ARBITRAJE!**\n\n"
                    f"🔹 **Comprar:** {res['buy']:.2f} {FIAT}\n"
                    f"🔹 **Vender:** {res['sell']:.2f} {FIAT}\n\n"
                    f"⚡ **Spread Neto:** `{res['spread_net']:.2f}%`\n"
                    f"📊 **Tendencia:** {calculate_trend()}"
                )
                await app.bot.send_message(
                    chat_id=CHAT_ID_NOTIFICACIONES, 
                    text=alert_msg, 
                    parse_mode="Markdown"
                )

        # Intervalo de 120 segundos (2 minutos) para registrar precios
        await asyncio.sleep(120)

async def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("historial", historial))

    asyncio.create_task(monitor_market(app))

    print("Bot corriendo correctamente con guardado histórico...")
    
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
