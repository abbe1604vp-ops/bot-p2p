import os
import logging
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURACIÓN DE LOGS ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- VARIABLES DE ENTORNO ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- CONFIGURACIÓN DE API CEDULA (OPCIÓN A) ---
CEDULA_API_URL = "https://tu-proveedor-api.com/v1/consulta"
CEDULA_API_TOKEN = "TU_TOKEN_AQUI"

# --- OBTENER PRECIOS DE BINANCE P2P (BANCO DE VENEZUELA) ---
def get_p2p_price():
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    payload_sell = {
        "asset": "USDT",
        "fiat": "VES",
        "tradeType": "BUY",
        "page": 1,
        "rows": 5,
        "payTypes": ["BANK_OF_VENEZUELA"]
    }

    payload_buy = {
        "asset": "USDT",
        "fiat": "VES",
        "tradeType": "SELL",
        "page": 1,
        "rows": 5,
        "payTypes": ["BANK_OF_VENEZUELA"]
    }

    try:
        res_sell = requests.post(url, json=payload_sell, headers=headers, timeout=5)
        data_sell = res_sell.json()
        price_sell = float(data_sell["data"][0]["adv"]["price"]) if data_sell.get("data") else 0.0

        res_buy = requests.post(url, json=payload_buy, headers=headers, timeout=5)
        data_buy = res_buy.json()
        price_buy = float(data_buy["data"][0]["adv"]["price"]) if data_buy.get("data") else 0.0

        return round(price_sell, 2), round(price_buy, 2)
    except Exception as e:
        logging.error(f"Error consultando Binance P2P: {e}")
        return 0.0, 0.0

def consultar_cedula_api(cedula: str) -> dict:
    headers = {
        "Authorization": f"Bearer {CEDULA_API_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {"cedula": cedula}
    try:
        response = requests.get(CEDULA_API_URL, params=params, headers=headers, timeout=8)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logging.error(f"Error consultando API de cédula: {e}")
    return None

# --- COMANDOS DEL BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot de Consulta P2P Activo*\n\n"
        "Comandos disponibles:\n"
        "• `/status` - Consulta tasas P2P (Banco de Venezuela)\n"
        "• `/cedula V12345678` - Consultar datos de persona",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("🔄 Consultando Binance P2P (Banco de Venezuela)...")
    sell_p, buy_p = get_p2p_price()

    if sell_p > 0 and buy_p > 0:
        spread = round(sell_p - buy_p, 2)
        respuesta = (
            f"📊 *ESTADO MERCADO P2P (BANCO DE VENEZUELA)*\n"
            f"──────────────────────────────\n"
            f"🟢 *Venta (Comprar USDT):* `{sell_p} VES`\n"
            f"🔴 *Recompra (Vender USDT):* `{buy_p} VES`\n"
            f"📐 *Spread:* `{spread} VES`\n"
            f"──────────────────────────────\n"
            f"⏰ *Hora:* `{datetime.now().strftime('%I:%M:%S %p')}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se pudieron obtener los precios de Binance P2P.")

async def buscar_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Ejemplo: `/cedula V12345678`", parse_mode="Markdown")
        return

    cedula_input = context.args[0].upper().replace(".", "").replace("-", "")
    msg_wait = await update.message.reply_text("🔍 Consultando datos...")

    datos = consultar_cedula_api(cedula_input)

    if datos and datos.get("status") == "success":
        nombre = datos.get("nombre_completo", "No registrado")
        estado = datos.get("estado", "N/A")
        centro = datos.get("centro_electoral", "N/A")

        respuesta = (
            f"👤 *DATOS ENCONTRADOS*\n"
            f"🪪 *Cédula:* `{cedula_input}`\n"
            f"✍️ *Nombre:* `{nombre}`\n"
            f"📍 *Estado:* `{estado}`\n"
            f"🏛️ *Centro:* `{centro}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se encontraron datos.")

# --- INICIALIZACIÓN ---
def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("No se encontró la variable TELEGRAM_BOT_TOKEN.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("cedula", buscar_cedula))

    print("🚀 Bot iniciado correctamente.")
    app.run_polling()

if __name__ == "__main__":
    main()
