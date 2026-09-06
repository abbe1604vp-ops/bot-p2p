import os
from google import genai
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# Configurar el cliente de la IA de Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def preguntar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para hacerle preguntas a la IA."""
    if not context.args:
        await update.message.reply_text("❓ *Uso:* `/preguntar ¿Qué es el spread en P2P?`", parse_mode="Markdown")
        return

    prompt = " ".join(context.args)
    msg_wait = await update.message.reply_text("🤖 Pensando respuesta...")

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        
        # Enviar la respuesta generada por la IA
        await msg_wait.edit_text(response.text)
    except Exception as e:
        await msg_wait.edit_text(f"⚠️ Ocurrió un error al consultar la IA: {e}")
