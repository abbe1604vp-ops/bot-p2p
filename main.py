import os
import logging
import requests
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_CHAT_IDS = set()

DB_NAME = "p2p_data.db"

# ---------------------------------------------------------
# FUNCIONES DE BASE DE DATOS (SQLITE)
# ---------------------------------------------------------
def init_db():
    """Crea la tabla de historial si no existe."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            compra REAL NOT NULL,
            venta REAL NOT NULL,
            spread REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def guardar_registro(compra, venta, spread):
    """Inserta una nueva lectura de precios en la base de datos."""
    now_ve = get_venezuela_time()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO historial (timestamp, fecha, hora, compra, venta, spread)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        now_ve.isoformat(),
        now_ve.strftime("%Y-%m-%d"),
        now_ve.strftime("%I:%M %p"),
        compra,
        venta,
        spread
    ))
    conn.commit()
    conn.close()

def obtener_historial_reciente(limite=300):
    """Obtiene las últimas lecturas almacenadas para análisis y gráficos."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT hora, compra, venta, spread, fecha FROM historial
        ORDER BY id DESC LIMIT ?
    ''', (limite,))
    registros = cursor.fetchall()
    conn.close()
    
    # Invertir para orden cronológico
    return list(reversed(registros))

# ---------------------------------------------------------
# CONSULTA DE APIS DE PRECIO
# ---------------------------------------------------------
def get_p2p_price():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Fuente 1: CriptoYa (P2P BDV)
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

# ---------------------------------------------------------
# COMPONENTES VISUALES Y CÁLCULOS
# ---------------------------------------------------------
def generate_chart_url(history):
    labels = [h[0] for h in history[-15:]]
    data_compra = [h[1] for h in history[-15:]]
    data_venta = [h[2] for h in history[-15:]]

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
            "title": {"display": True, "text": "Histórico Guardado Binance P2P BDV"},
            "scales": {"yAxes": [{"ticks": {"beginAtZero": False}}]}
        }
    }
    chart_json = json.dumps(chart_config)
    return f"https://quickchart.io/chart?c={requests.utils.quote(chart_json)}&w=500&h=300&bkg=white"

def calcular_prediccion_db(history):
    if len(history) < 2:
        return "NEUTRAL 🟡", 0.0, []

    compras = [h[1] for h in history]
    ventas = [h[2] for h in history]

    n = len(compras)
    delta_c = (compras[-1] - compras[0]) / n
    delta_v = (ventas[-1] - ventas[0]) / n

    tendencia = "ALCISTA 🟢" if delta_c >= 0 else "BAJISTA 🔴"

    proyecciones = []
    horizontes = [("1h", 20), ("3h", 60), ("6h", 120), ("12h", 240)]

    for h_label, pasos in horizontes:
        pred_compra = round(compras[-1] + (delta_c * pasos), 2)
        pred_venta = round(ventas[-1] + (delta_v * pasos), 2)

        flecha_c = "↗️ 🟢" if delta_c >= 0 else "↘️ 🔴"
        flecha_v = "↗️ 🟢" if delta_v >= 0 else "↘️ 🔴"

        proyecciones.append({
            "hora": h_label,
            "compra": pred_compra,
            "flecha_c": flecha_c,
            "venta": pred_venta,
            "flecha_v": flecha_v
        })

    return tendencia, round(delta_c, 3), proyecciones

# ---------------------------------------------------------
# COMANDOS DE TELEGRAM
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    await update.message.reply_text(
        "🤖 *Bot Binance P2P con Base de Datos SQL*\n\n"
        "• `/status` : Precios actualizados y spread.\n"
        "• `/grafico` : Histórico dinámico desde la BD.\n"
        "• `/prediccion` : Análisis de tendencia basado en lecturas guardadas.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P BDV...")
    
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
            f"💾 *Registro guardado en base de datos.*"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ Error al consultar la API.")

async def prediccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    history = obtener_historial_reciente(limite=200)

    if len(history) < 3:
        await update.message.reply_text("⏳ Esperando más registros en la base de datos para realizar la predicción...")
        return

    msg_wait = await update.message.reply_text("🧠 Consultando BD y analizando tendencia...")

    tendencia, ritmo, proyecciones = calcular_prediccion_db(history)
    hora_actual = history[-1][0]

    texto_prediccion = (
        f"🔮 *PREDICCIÓN BASADA EN HISTORIAL (BD)*\n"
        f"──────────────────────────────\n"
        f"⏰ *Última Lectura BD:* `{hora_actual}`\n"
        f"📊 *Tendencia Base:* *{tendencia}*\n"
        f"──────────────────────────────\n"
        f"📌 *PROYECCIÓN RESTO DEL DÍA:*\n\n"
    )

    for p in proyecciones:
        texto_prediccion += (
            f"⏱️ *En +{p['hora']}:*\n"
            f"  🟢 Comprar: `{p['compra']} VES` {p['flecha_c']}\n"
            f"  🔴 Vender: `{p['venta']} VES` {p['flecha_v']}\n\n"
        )

    texto_prediccion += "💾 *Análisis generado con datos persistentes en SQLite.*"
    await msg_wait.edit_text(texto_prediccion, parse_mode="Markdown")

async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CHAT_IDS.add(update.effective_chat.id)
    history = obtener_historial_reciente(limite=100)

    if len(history) < 2:
        await update.message.reply_text("⏳ Base de datos inicializándose... Intenta de nuevo en unos minutos.")
        return

    msg_wait = await update.message.reply_text("📊 Consultando BD y generando gráfico...")

    compras = [h[1] for h in history]
    ventas = [h[2] for h in history]
    ultima_hora = history[-1][0]

    chart_url = generate_chart_url(history)

    caption_text = (
        f"📈 *ANÁLISIS DESDE BASE DE DATOS*\n"
        f"──────────────────────────────\n"
        f"🏔️ *Techo Histórico:* Comprar `{max(compras)} VES` | Vender `{max(ventas)} VES`\n"
        f"🏕️ *Piso Histórico:* Comprar `{min(compras)} VES` | Vender `{min(ventas)} VES`\n"
        f"⏰ *Hora:* `{ultima_hora}`"
    )

    try:
        await update.message.reply_photo(photo=chart_url, caption=caption_text, parse_mode="Markdown")
        await msg_wait.delete()
    except Exception as e:
        logging.error(f"Error gráfico: {e}")
        await msg_wait.edit_text("❌ Error al renderizar la imagen desde la BD.")

# ---------------------------------------------------------
# TAREA EN SEGUNDO PLANO (MONITOREO + ALERTA + GUARDADO)
# ---------------------------------------------------------
async def background_monitoring(context: ContextTypes.DEFAULT_TYPE):
    sell_p, buy_p = get_p2p_price()
    if sell_p > 0 and buy_p > 0:
        spread_ves = round(abs(sell_p - buy_p), 2)
        now_ve = get_venezuela_time()
        hora_str = now_ve.strftime("%I:%M %p")

        # 1. Guardar en SQLite
        try:
            guardar_registro(sell_p, buy_p, spread_ves)
        except Exception as e:
            logging.error(f"Error al guardar en DB: {e}")

        # 2. Enviar Alertas de Spread >= 10 VES
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

    # Inicializar Base de Datos
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("grafico", grafico))
    app.add_handler(CommandHandler("prediccion", prediccion))

    # Guardar en base de datos cada 3 minutos (180 segundos)
    if app.job_queue:
        app.job_queue.run_repeating(background_monitoring, interval=180, first=5)

    print("🚀 Bot iniciado con persistencia de Base de Datos SQLite...")
    app.run_polling()

if __name__ == "__main__":
    main()
