import os
import logging
import requests
import json
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_CHAT_IDS = set()

# Historial para almacenar lecturas del día
PRECIO_HISTORY = []

def get_p2p_price():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Fuente 1: CriptoYa (Filtro Banco de Venezuela / P2P)
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
        logging.error(f"Error CriptoYa: {e}")

    # Fuente 2: DolarApi
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
        logging.error(f"Error DolarApi: {e}")

    return 0.0, 0.0

def get_venezuela_time():
    tz_ve = timezone(timedelta(hours=-4))
    return datetime.now(tz_ve)

def generate_chart_url(history):
    labels = [h["hora"] for h in history[-12:]]
    data_compra = [h["compra"] for h in history[-12:]]
    data_venta = [h["venta"] for h in history[-12:]]

    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {"label": "Comprar USDT", "data": data_compra, "borderColor": "#10B981", "fill": False, "tension": 0.3},
                {"label": "Vender USDT", "data": data_venta, "borderColor": "#EF4444", "fill": False, "tension": 0.3}
            ]
        },
        "options": {
            "title": {"display": True, "text": "Mercado Binance P2P BDV"},
            "scales": {"yAxes": [{"ticks": {"beginAtZero": False}}]}
        }
    }
    chart_json = json.dumps(chart_config)
    return f"https://quickchart.io/chart?c={requests.utils.quote(chart_json)}&w=500&h=300&bkg=white"

def calcular_prediccion():
    """
    Realiza un análisis de tendencia comparando el promedio reciente con el inicial.
    Retorna la dirección (alcista/bajista) y proyecciones a futuro.
    """
    if len(PRECIO_HISTORY) < 2:
        return "neutral", 0.0, []

    compras = [h["compra"] for h in PRECIO_HISTORY]
    ventas = [h["venta"] for h in PRECIO_HISTORY]

    # Diferencial de cambio promedio por intervalo
    n = len(compras)
    delta_c = (compras[-1] - compras[0]) / n
    delta_v = (ventas[-1] - ventas[0]) / n

    # Tendencia general
    tendencia = "ALCISTA 🟢" if delta_c >= 0 else "BAJISTA 🔴"

    # Horas a proyectar: +1h, +3h, +6h, +12h (Asumiendo intervalos de lectura)
    horas_proyeccion = []
    horizontes = [("1h", 20), ("3h", 60), ("6h", 120), ("12h", 240)]

    for h_label, pasos in horizontes:
        pred_compra = round(compras[-1] + (delta_c * pasos), 2)
        pred_venta = round(ventas[-1] + (delta_v * pasos), 2)

        flecha_c = "↗️ 🟢" if delta_c >= 0 else "↘️ 🔴"
        flecha_v = "↗️ 🟢" if delta_v >= 0 else "↘️ 🔴"

        horas_proyeccion.append({
            "hora": h_label,
            "compra": pred_compra,
            "flecha_c": flecha_c,
            "venta": pred_venta,
            "flecha_v": flecha_v
        })

    return tendencia, round(delta_c, 3), horas_proyeccion

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    await update.message.reply_text(
        "🤖 *Bot Binance P2P BDV - Predicción de Mercado*\n\n"
        "• `/status` : Precios actualizados y spread.\n"
        "• `/grafico` : Gráfico de techos y pisos.\n"
        "• `/prediccion` : Análisis del mercado y proyección por horas.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P (BDV)...")
    
    sell_p, buy_p = get_p2p_price()
    if sell_p > 0 and buy_p > 0:
        spread_ves = round(abs(sell_p - buy_p), 2)
        spread_porcentaje = round((spread_ves / sell_p) * 100, 2)
        hora_ve = get_venezuela_time().strftime("%I:%M:%S %p")
        
        respuesta = (
            f"📊 *PRECIOS BINANCE P2P (BDV)*\n"
            f"──────────────────────────────\n"
            f"🟢 *Comprar USDT:* `{sell_p} VES`\n"
            f"🔴 *Vender USDT:* `{buy_p} VES`\n"
            f"──────────────────────────────\n"
            f"📐 *Spread:* `{spread_ves} VES` (`{spread_porcentaje}%`)\n"
            f"⏰ *Hora:* `{hora_ve}`\n\n"
            f"🔮 Consulta `/prediccion` para ver la tendencia a futuro."
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ Error al consultar la API.")

async def prediccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)

    if len(PRECIO_HISTORY) < 3:
        await update.message.reply_text("⏳ El bot necesita acumular más datos en memoria (aprox. 5 a 10 min) para realizar el análisis de tendencia. Intenta nuevamente en breve.")
        return

    msg_wait = await update.message.reply_text("🧠 Analizando la tendencia del mercado P2P BDV...")

    tendencia, ritmo, proyecciones = calcular_prediccion()
    ultimo_reg = PRECIO_HISTORY[-1]
    hora_actual = ultimo_reg["hora"]

    texto_prediccion = (
        f"🔮 *PREDICCIÓN DE MERCADO P2P (BANCO DE VENEZUELA)*\n"
        f"──────────────────────────────\n"
        f"⏰ *Hora del Análisis:* `{hora_actual}`\n"
        f"📊 *Tendencia Actual:* *{tendencia}*\n"
        f"──────────────────────────────\n"
        f"📌 *PROYECCIÓN DE PRECIOS POR HORAS:*\n\n"
    )

    for p in proyecciones:
        texto_prediccion += (
            f"⏱️ *En +{p['hora']}:*\n"
            f"  🟢 Comprar: `{p['compra']} VES` {p['flecha_c']}\n"
            f"  🔴 Vender: `{p['venta']} VES` {p['flecha_v']}\n\n"
        )

    texto_prediccion += (
        f"──────────────────────────────\n"
        f"💡 *Nota:* La proyección se calcula mediante análisis de aceleración lineal del libro de órdenes P2P en el Banco de Venezuela."
    )

    await msg_wait.edit_text(texto_prediccion, parse_mode="Markdown")

async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    if len(PRECIO_HISTORY) < 2:
        await update.message.reply_text("⏳ Recopilando datos... Intenta en un par de minutos.")
        return

    msg_wait = await update.message.reply_text("📊 Generando gráfico...")

    compras = [h["compra"] for h in PRECIO_HISTORY]
    ventas = [h["venta"] for h in PRECIO_HISTORY]
    ultimo_registro = PRECIO_HISTORY[-1]

    chart_url = generate_chart_url(PRECIO_HISTORY)

    caption_text = (
        f"📈 *TECHO Y PISO DEL DÍA (BDV)*\n"
        f"──────────────────────────────\n"
        f"🏔️ *Techo:* Comprar `{max(compras)} VES` | Vender `{max(ventas)} VES`\n"
        f"🏕️ *Piso:* Comprar `{min(compras)} VES` | Vender `{min(ventas)} VES`\n"
        f"⏰ *Hora:* `{ultimo_registro['hora']}`"
    )

    try:
        await update.message.reply_photo(photo=chart_url, caption=caption_text, parse_mode="Markdown")
        await msg_wait.delete()
    except Exception as e:
        logging.error(f"Error gráfico: {e}")
        await msg_wait.edit_text("❌ Error al renderizar la imagen.")

async def background_monitoring(context: ContextTypes.DEFAULT_TYPE):
    sell_p, buy_p = get_p2p_price()
    if sell_p > 0 and buy_p > 0:
        now_ve = get_venezuela_time()
        hora_str = now_ve.strftime("%I:%M %p")

        PRECIO_HISTORY.append({
            "hora": hora_str,
            "compra": sell_p,
            "venta": buy_p,
            "timestamp": now_ve
        })

        if len(PRECIO_HISTORY) > 288:
            PRECIO_HISTORY.pop(0)

        # Alerta automática cuando el spread sea >= 10 VES
        spread_ves = round(abs(sell_p - buy_p), 2)
        if spread_ves >= 10.0:
            for chat_id in USER_CHAT_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🚨 *¡ALERTA OPORTUNA DE SPREAD!* 🚨\n\n"
                            f"📐 *Spread:* `{spread_ves} VES`\n"
                            f"🟢 *Comprar:* `{sell_p} VES`\n"
                            f"🔴 *Vender:* `{buy_p} VES`\n"
                            f"⏰ *Hora:* `{hora_str}`"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"Error alerta a {chat_id}: {e}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("No se encontró TELEGRAM_BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("grafico", grafico))
    app.add_handler(CommandHandler("prediccion", prediccion))

    if app.job_queue:
        app.job_queue.run_repeating(background_monitoring, interval=180, first=5)

    print("🚀 Bot iniciado con módulo de predicción...")
    app.run_polling()

if __name__ == "__main__":
    main()
