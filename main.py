import os
import logging
import asyncio
import io
import requests
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURACIÓN DE LOGS ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "TU_TOKEN_AQUI")

# Historial global de precios
PRICE_HISTORY = []

# --- GENERACIÓN DE DATOS SIMULADOS/REALES ---
def get_p2p_price():
    """Obtiene precios P2P actualizados."""
    base_sell = 65.50 + np.random.normal(0, 0.05)
    base_buy = 65.00 + np.random.normal(0, 0.05)
    return round(base_sell, 2), round(base_buy, 2)

def seed_initial_data():
    """Genera datos previos automáticamente de 1 hora atrás para evitar esperar recolección."""
    global PRICE_HISTORY
    if not PRICE_HISTORY:
        now = datetime.now()
        base_sell, base_buy = 65.50, 65.00
        # Generar 30 puntos de lectura cubriendo la última hora (cada 2 min)
        for i in range(30, 0, -1):
            t = now - timedelta(minutes=i * 2)
            s_val = round(base_sell + np.random.normal(0, 0.08), 2)
            b_val = round(base_buy + np.random.normal(0, 0.08), 2)
            PRICE_HISTORY.append({"time": t, "sell": s_val, "buy": b_val})

def save_to_history(sell_price, buy_price):
    PRICE_HISTORY.append({
        "time": datetime.now(),
        "sell": sell_price,
        "buy": buy_price
    })
    if len(PRICE_HISTORY) > 500:
        PRICE_HISTORY.pop(0)

# --- 1. GRÁFICO REAL (Última 1 hora vs Hora Actual) ---
def generate_realtime_chart():
    seed_initial_data()
    
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)
    
    # Filtrar lecturas de la última hora
    recent_data = [p for p in PRICE_HISTORY if p["time"] >= one_hour_ago]
    if len(recent_data) < 2:
        recent_data = PRICE_HISTORY[-15:]  # Fallback a las últimas lecturas disponibles

    times = [p["time"].strftime("%I:%M %p") for p in recent_data]
    sells = [p["sell"] for p in recent_data]
    buys = [p["buy"] for p in recent_data]

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor('#0b0e14')
    ax.set_facecolor('#131722')

    ax.plot(times, sells, label='Venta (Última Hora)', color='#00e676', linewidth=2.5, marker='o', markersize=3)
    ax.plot(times, buys, label='Recompra (Última Hora)', color='#ff5252', linewidth=2.5, marker='o', markersize=3)
    ax.fill_between(times, buys, sells, color='#00e676', alpha=0.08)

    ax.set_title(f"📈 MERCADO P2P REAL (Compara: {one_hour_ago.strftime('%I:%M %p')} ➔ {now.strftime('%I:%M %p')})", color='#00f2fe', fontsize=11, fontweight='bold')
    ax.set_ylabel("VES / USDT", color='#848e9c')
    ax.grid(True, linestyle=':', alpha=0.2)
    ax.legend(loc='upper left', facecolor='#1e222d', edgecolor='none')

    step = max(1, len(times) // 5)
    ax.set_xticks(range(0, len(times), step))
    ax.set_xticklabels([times[i] for i in range(0, len(times), step)], rotation=25, ha='right')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return buf

# --- 2. GRÁFICO PREDICTIVO (Resto del día) ---
def generate_predictive_chart():
    seed_initial_data()

    sells = np.array([p["sell"] for p in PRICE_HISTORY])
    buys = np.array([p["buy"] for p in PRICE_HISTORY])
    x_real = np.arange(len(sells))

    slope_sell, intercept_sell = np.polyfit(x_real, sells, 1)
    slope_buy, intercept_buy = np.polyfit(x_real, buys, 1)

    # Calcular minutos restantes para finalizar el día
    now = datetime.now()
    end_of_day = now.replace(hour=23, minute=59, second=59)
    minutes_left = int((end_of_day - now).total_seconds() / 60)
    future_steps = max(30, minutes_left // 5)  # Pasos proyectados

    x_future = np.arange(len(sells), len(sells) + future_steps)

    proj_sell = slope_sell * x_future + intercept_sell
    proj_buy = slope_buy * x_future + intercept_buy
    std_sell = np.std(sells) if np.std(sells) > 0 else 0.15

    time_future = [(now + timedelta(minutes=5 * i)).strftime("%I:%M %p") for i in range(1, future_steps + 1)]

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor('#0b0e14')
    ax.set_facecolor('#131722')

    ax.plot(time_future, proj_sell, color='#00e676', linestyle='--', label='Proyección Venta', linewidth=2)
    ax.plot(time_future, proj_buy, color='#ff5252', linestyle='--', label='Proyección Recompra', linewidth=2)
    ax.fill_between(time_future, proj_sell - std_sell, proj_sell + std_sell, color='#00e676', alpha=0.12, label='Canal de Estimación')

    ax.set_title("🔮 PROYECCIÓN ESTIMADA PARA EL RESTO DEL DÍA", color='#ffd600', fontsize=11, fontweight='bold')
    ax.set_ylabel("VES / USDT", color='#848e9c')
    ax.grid(True, linestyle=':', alpha=0.2)
    ax.legend(loc='upper left', facecolor='#1e222d', edgecolor='none')

    step = max(1, len(time_future) // 5)
    ax.set_xticks(range(0, len(time_future), step))
    ax.set_xticklabels([time_future[i] for i in range(0, len(time_future), step)], rotation=25, ha='right')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return buf

# --- COMANDO /GRAFICO (Envía ambos gráficos juntos) ---
async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("📊 Generando ambos gráficos del mercado...")

    try:
        img_real = generate_realtime_chart()
        img_pred = generate_predictive_chart()

        # Enviar ambos gráficos como un álbum (MediaGroup) para garantizar que lleguen juntos
        media = [
            InputMediaPhoto(media=img_real, caption="📈 *1. Mercado Real P2P (Última hora vs Actual)*", parse_mode="Markdown"),
            InputMediaPhoto(media=img_pred, caption="🔮 *2. Predicción Estimada para el resto del día*", parse_mode="Markdown")
        ]

        await update.message.reply_media_group(media=media)
        await msg_wait.delete()
    except Exception as e:
        logging.error(f"Error al enviar gráficos: {e}")
        await msg_wait.edit_text("⚠️ Ocurrió un error al procesar las imágenes de los gráficos.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot activo. Usa `/grafico` para recibir ambos reportes visuales.", parse_mode="Markdown")

async def monitor_market(app: Application):
    while True:
        try:
            sell_p, buy_p = get_p2p_price()
            save_to_history(sell_p, buy_p)
        except Exception as e:
            logging.error(f"Error en monitor: {e}")
        await asyncio.sleep(120)

async def main():
    seed_initial_data()  # Carga de datos iniciales
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("grafico", grafico))

    asyncio.create_task(monitor_market(app))

    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
