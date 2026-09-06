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

# Historial en memoria para almacenar lecturas del día
# Estructura: [{"hora": "02:30 PM", "compra": 45.2, "venta": 44.1, "timestamp": datetime}]
PRECIO_HISTORY = []

def get_p2p_price():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Fuente 1: CriptoYa
    try:
        url = "https://criptoya.com/api/binancep2p/usdt/ves/1"
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            ask = float(data.get("ask", 0.0))  # Comprar USDT (Venta)
            bid = float(data.get("bid", 0.0))  # Vender USDT (Recompra)
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
    """
    Genera una URL de QuickChart con las líneas de Compra y Venta.
    """
    labels = [h["hora"] for h in history[-12:]]  # Últimas 12 lecturas
    data_compra = [h["compra"] for h in history[-12:]]
    data_venta = [h["venta"] for h in history[-12:]]

    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Comprar USDT",
                    "data": data_compra,
                    "borderColor": "#10B981",
                    "fill": False,
                    "tension": 0.3
                },
                {
                    "label": "Vender USDT",
                    "data": data_venta,
                    "borderColor": "#EF4444",
                    "fill": False,
                    "tension": 0.3
                }
            ]
        },
        "options": {
            "title": {"display": True, "text": "Tendencia Binance P2P VES"},
            "scales": {
                "yAxes": [{"ticks": {"beginAtZero": False}}]
            }
        }
    }
    
    chart_json = json.dumps(chart_config)
    return f"https://quickchart.io/chart?c={requests.utils.quote(chart_json)}&w=500&h=300&bkg=white"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    await update.message.reply_text(
        "🤖 *Bot Binance P2P con Gráficos y Proyección*\n\n"
        "• `/status` : Ver precios actuales y alertas.\n"
        "• `/grafico` : Generar gráfico del día con techos, pisos y proyección.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P...")
    
    sell_p, buy_p = get_p2p_price()
    if sell_p > 0 and buy_p > 0:
        spread_ves = round(abs(sell_p - buy_p), 2)
        spread_porcentaje = round((spread_ves / sell_p) * 100, 2)
        hora_ve = get_venezuela_time().strftime("%I:%M:%S %p")
        
        respuesta = (
            f"📊 *PRECIOS BINANCE P2P*\n"
            f"──────────────────────────────\n"
            f"🟢 *Comprar USDT:* `{sell_p} VES`\n"
            f"🔴 *Vender USDT:* `{buy_p} VES`\n"
            f"──────────────────────────────\n"
            f"📐 *Spread:* `{spread_ves} VES` (`{spread_porcentaje}%`)\n"
            f"⏰ *Hora:* `{hora_ve}`\n\n"
            f"📈 Usa `/grafico` para ver techos, pisos y proyección."
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ Error al consultar la API.")

async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    
    if len(PRECIO_HISTORY) < 2:
        await update.message.reply_text("⏳ Recopilando datos suficientes para el gráfico... Intenta de nuevo en un par de minutos.")
        return

    msg_wait = await update.message.reply_text("📊 Generando gráfico y calculando proyección...")

    # Extraer Techos y Pisos
    compras = [h["compra"] for h in PRECIO_HISTORY]
    ventas = [h["venta"] for h in PRECIO_HISTORY]

    techo_compra, piso_compra = max(compras), min(compras)
    techo_venta, piso_venta = max(ventas), min(ventas)

    # Precios actuales y hora
    ultimo_registro = PRECIO_HISTORY[-1]
    precio_actual_compra = ultimo_registro["compra"]
    precio_actual_venta = ultimo_registro["venta"]
    hora_actual = ultimo_registro["hora"]

    # Cálculo de Proyección (Tendencia basada en las últimas lecturas)
    delta_compra = PRECIO_HISTORY[-1]["compra"] - PRECIO_HISTORY[0]["compra"]
    delta_venta = PRECIO_HISTORY[-1]["venta"] - PRECIO_HISTORY[0]["venta"]

    proj_compra = round(precio_actual_compra + (delta_compra * 0.5), 2)
    proj_venta = round(precio_actual_venta + (delta_venta * 0.5), 2)

    # Generar la imagen del gráfico
    chart_url = generate_chart_url(PRECIO_HISTORY)

    caption_text = (
        f"📈 *ANÁLISIS DE MERCADO P2P*\n"
        f"──────────────────────────────\n"
        f"⏰ *Hora de solicitud:* `{hora_actual}`\n"
        f"🟢 *Comprar Actual:* `{precio_actual_compra} VES`\n"
        f"🔴 *Vender Actual:* `{precio_actual_venta} VES`\n\n"
        f"🏔️ *TECHOS DEL DÍA (MÁXIMOS):*\n"
        f"• Comprar: `{techo_compra} VES` | Vender: `{techo_venta} VES`\n\n"
        f"🏕️ *PISOS DEL DÍA (MÍNIMOS):*\n"
        f"• Comprar: `{piso_compra} VES` | Vender: `{piso_venta} VES`\n\n"
        f"🔮 *PROYECCIÓN RESTO DEL DÍA:*\n"
        f"• Comprar Est.: `{proj_compra} VES`\n"
        f"• Vender Est.: `{proj_venta} VES`"
    )

    try:
        await update.message.reply_photo(photo=chart_url, caption=caption_text, parse_mode="Markdown")
        await msg_wait.delete()
    except Exception as e:
        logging.error(f"Error enviando gráfico: {e}")
        await msg_wait.edit_text("❌ Ocurrió un problema al renderizar el gráfico.")

# Tarea periódica para almacenar precios y evaluar alertas
async def background_monitoring(context: ContextTypes.DEFAULT_TYPE):
    sell_p, buy_p = get_p2p_price()
    if sell_p > 0 and buy_p > 0:
        now_ve = get_venezuela_time()
        hora_str = now_ve.strftime("%I:%M %p")

        # Guardar en el historial
        PRECIO_HISTORY.append({
            "hora": hora_str,
            "compra": sell_p,
            "venta": buy_p,
            "timestamp": now_ve
        })

        # Limpiar registros más antiguos a 24 horas
        if len(PRECIO_HISTORY) > 288:  # 288 lecturas = 24h a 5 min intervalo
            PRECIO_HISTORY.pop(0)

        # Evaluar Alerta de Spread >= 10 VES
        spread_ves = round(abs(sell_p - buy_p), 2)
        if spread_ves >= 10.0:
            for chat_id in USER_CHAT_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🚨 *¡ALERTA OPORTUNA DE SPREAD!* 🚨\n\n"
                            f"📐 *Spread Actual:* `{spread_ves} VES`\n"
                            f"🟢 *Comprar USDT:* `{sell_p} VES`\n"
                            f"🔴 *Vender USDT:* `{buy_p} VES`\n"
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

    # Guardar precios en historial cada 3 minutos (180s)
    if app.job_queue:
        app.job_queue.run_repeating(background_monitoring, interval=180, first=5)

    print("🚀 Bot iniciado con análisis de gráficos...")
    app.run_polling()

if __name__ == "__main__":
    main()
