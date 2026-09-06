import asyncio
import logging
import requests
import csv
import io
from datetime import datetime, timezone, timedelta
from collections import deque

import matplotlib
matplotlib.use('Agg')  # Modo sin interfaz gráfica para servidores como Render
import matplotlib.pyplot as plt

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURACIÓN ---
TELEGRAM_BOT_TOKEN = "6327813571:AAEeCbTsLE43btjzbMCpJ0j6yAJWzu-3Zd8"
CHAT_ID_NOTIFICACIONES = None

FIAT = "VES"
ASSET = "USDT"
COMMISSION_PERCENT = 0.35
MIN_SPREAD_ALERT = 1.0

# Intervalo para enviar la gráfica automática en segundos (ejemplo: 3600 s = 1 hora)
AUTO_GRAPH_INTERVAL = 3600 

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
CSV_FILE = "historial_p2p.csv"

# Zona horaria Venezuela (UTC-4)
VET = timezone(timedelta(hours=-4))

# Historial para graficar (hasta 720 lecturas = 24 horas a 2 min/lectura)
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
    if len(PRICE_HISTORY) < 5:
        return "⏳ Analizando flujo de mercado..."

    recent_sells = [p["sell"] for p in list(PRICE_HISTORY)[-10:]]
    diff_pct = ((recent_sells[-1] - recent_sells[0]) / recent_sells[0]) * 100

    if diff_pct >= 0.3:
        return "🚀 ALCISTA FUERTE"
    elif diff_pct >= 0.1:
        return "↗️ LATERAL CON SESGO ALCISTA"
    elif diff_pct <= -0.3:
        return "📉 BAJISTA ACELERADO"
    elif diff_pct <= -0.1:
        return "↘️ LATERAL CON SESGO BAJISTA"
    else:
        return "➡️ LATERAL ESTABLE"

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

def generate_chart_image():
    """Genera una imagen tipo panel oscuro con las curvas de tasa de venta/recompra y extensión de mercado."""
    if len(PRICE_HISTORY) < 2:
        return None

    times = [p["time"].strftime("%I:%M %p") for p in PRICE_HISTORY]
    sells = [p["sell"] for p in PRICE_HISTORY]
    buys = [p["buy"] for p in PRICE_HISTORY]
    spreads = [p["spread_net"] for p in PRICE_HISTORY]

    max_sell = max(sells)
    min_buy = min(buys)
    max_spread = max(spreads)
    current_bias = get_market_bias()

    # Configuración de estética oscura estilo ArBit
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), gridspec_kw={'height_ratios': [2.5, 1]}, sharex=True)
    fig.patch.set_facecolor('#0b0e14')
    ax1.set_facecolor('#131722')
    ax2.set_facecolor('#131722')

    # Título y métricas de cabecera
    header_text = f"TECHO: {max_sell:.2f} VES   |   PISO: {min_buy:.2f} VES   |   SPREAD MÁX: {max_spread:.2f}%   |   SESGO: {current_bias}"
    fig.suptitle(header_text, fontsize=10, color='#00f2fe', fontweight='bold', y=0.96)

    # Subplot 1: Curva de precios Venta y Recompra
    ax1.plot(times, sells, label='Tasa Venta (P2P)', color='#00e676', linewidth=2)
    ax1.plot(times, buys, label='Tasa Recompra (P2P)', color='#ff5252', linewidth=2)
    ax1.fill_between(times, buys, sells, color='#00e676', alpha=0.08)
    ax1.axhline(max_sell, color='#00e676', linestyle='--', alpha=0.4, label=f'Techo ({max_sell:.2f})')
    ax1.axhline(min_buy, color='#ff5252', linestyle='--', alpha=0.4, label=f'Piso ({min_buy:.2f})')
    ax1.set_ylabel('VES / USDT', color='#848e9c')
    ax1.legend(loc='upper left', fontsize=8, facecolor='#1e222d', edgecolor='none')
    ax1.grid(True, linestyle=':', alpha=0.2)

    # Subplot 2: Margen Neto / Impulso de Spread
    colors = ['#00e676' if s >= 1.0 else '#2962ff' for s in spreads]
    ax2.bar(times, spreads, color=colors, alpha=0.7, width=0.6)
    ax2.axhline(1.0, color='#ffd600', linestyle=':', alpha=0.7, label='Umbral Alerta (1.0%)')
    ax2.set_ylabel('Spread Neto %', color='#848e9c')
    ax2.grid(True, linestyle=':', alpha=0.2)

    # Formateo de ejes
    step = max(1, len(times) // 8)
    ax2.set_xticks(range(0, len(times), step))
    ax2.set_xticklabels([times[i] for i in range(0, len(times), step)], rotation=30, ha='right', fontsize=8)

    plt.tight_layout(rect=[0, 0, 1, 0.93])

    # Guardar en memoria RAM para enviar a Telegram sin crear archivos temporales
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    img_buf.seek(0)
    plt.close(fig)

    return img_buf

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_NOTIFICACIONES
    CHAT_ID_NOTIFICACIONES = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 *BOT DE MONITOREO Y GRÁFICOS P2P*\n\n"
        f"Par: *{ASSET}/{FIAT}*\n"
        f"Generador de gráficos analíticos activo.\n\n"
        f"📋 *Comandos:*\n"
        f"• /status — Estado actual del mercado\n"
        f"• /grafico — Generar reporte gráfico del día\n"
        f"• /senales — Puntos óptimos y sesgo\n"
        f"• /historial — Estadísticas de lecturas acumuladas",
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
        f"📁 *Lecturas:* `{len(PRICE_HISTORY)} acumuladas`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("📈 Generando gráfico de fluctuación diaria...")
    img = generate_chart_image()
    if img:
        await update.message.reply_photo(photo=img, caption="📊 *Proyección y Comportamiento del Mercado USDT/VES*", parse_mode="Markdown")
        await msg_wait.delete()
    else:
        await msg_wait.edit_text("⏳ Se necesitan al menos 2 lecturas acumuladas para graficar.")

async def senales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = calculate_arbitrage()
    if not res:
        await update.message.reply_text("⚠️ Error al procesar precios.")
        return

    signals = get_market_signals(res["buy"], res["sell"])
    bias = get_market_bias()

    if not signals:
        await update.message.reply_text("⏳ Recopilando datos de tendencia...")
        return

    sig_header = "🔍 *ANÁLISIS TÉCNICO Y SEÑALES*"
    action_rec = "Mantener posición / Monitorear"
    if signals["signal"] == "PUNTO_VENTA_OPTIMO":
        sig_header = "🔴 *PUNTO DE VENTA ÓPTIMO — Confirmado*"
        action_rec = "¡VENDER AHORA!"
    elif signals["signal"] == "PUNTO_RECOMPRA_OPTIMO":
        sig_header = "🟢 *PUNTO DE RECOMPRA ÓPTIMO — Confirmado*"
        action_rec = "¡RECOMPRAR AHORA!"

    msg = (
        f"{sig_header}\n"
        f"──────────────────────────────\n"
        f"🎯 *Recomendación:* `{action_rec}`\n"
        f"📉 *Sesgo:* {bias}\n\n"
        f"🔹 *Venta Actual:* `{res['sell']:.2f} {FIAT}`\n"
        f"🔹 *Compra Actual:* `{res['buy']:.2f} {FIAT}`\n"
        f"⚡ *Spread Neto:* `{res['spread_net']:.2f}%`"
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
        f"• *Archivo CSV:* `historial_p2p.csv`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def auto_graph_loop(app: Application):
    """Bucle programado para enviar la gráfica automáticamente cada cierto tiempo (ej: cada 1 hora)."""
    while True:
        await asyncio.sleep(AUTO_GRAPH_INTERVAL)
        if CHAT_ID_NOTIFICACIONES and len(PRICE_HISTORY) >= 2:
            img = generate_chart_image()
            if img:
                await app.bot.send_photo(
                    chat_id=CHAT_ID_NOTIFICACIONES,
                    photo=img,
                    caption="📈 *REPORTE PROGRAMADO DE FLUCTUACIÓN Y SPREAD*",
                    parse_mode="Markdown"
                )

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
                    await app.bot.send_message(chat_id=CHAT_ID_NOTIFICACIONES, text=alert_msg, parse_mode="Markdown")

        await asyncio.sleep(120)

async def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("grafico", grafico))
    app.add_handler(CommandHandler("senales", senales))
    app.add_handler(CommandHandler("historial", historial))

    # Tareas en segundo plano
    asyncio.create_task(monitor_market(app))
    asyncio.create_task(auto_graph_loop(app))

    print("Bot activo con envío automático y manual de gráficos...")
    
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
