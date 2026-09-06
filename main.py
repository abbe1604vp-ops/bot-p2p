import os
import logging
import requests
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
CEDULA_API_TOKEN = "6327813571:AAFeaShFa5UsP3IN73rtfcn5Lv_PMI953Yc"

def consultar_cedula_api(cedula: str) -> dict:
    """Realiza la consulta a la API de terceros."""
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
    """Comando /start"""
    await update.message.reply_text(
        "🤖 *Bot de Consulta Activo*\n\n"
        "Comandos disponibles:\n"
        "• `/cedula V12345678` - Consultar datos de persona.",
        parse_mode="Markdown"
    )

async def buscar_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /cedula V12345678"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Uso incorrecto del comando.*\n"
            "Ejemplo: `/cedula V12345678`",
            parse_mode="Markdown"
        )
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
            f"──────────────────────────────\n"
            f"🪪 *Cédula:* `{cedula_input}`\n"
            f"✍️ *Nombre:* `{nombre}`\n"
            f"📍 *Estado:* `{estado}`\n"
            f"🏛️ *Centro:* `{centro}`"
        )
        await msg_wait.edit_text(respuesta, parse_mode="Markdown")
    else:
        await msg_wait.edit_text("❌ No se encontraron resultados o la API no responde.")

# --- INICIALIZACIÓN PRINCIPAL ---
def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("No se encontró la variable TELEGRAM_BOT_TOKEN.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Registrar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cedula", buscar_cedula))

    print("🚀 Bot iniciado correctamente.")
    app.run_polling()

if __name__ == "__main__":
    main()
