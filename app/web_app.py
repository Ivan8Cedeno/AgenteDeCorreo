from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app.gmail_service import GmailService
from app.llm_service import LLMService
from app.whatsapp_service import WhatsAppService

BASE_DIR = Path(__file__).resolve().parent.parent
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
service = WhatsAppService()


@app.route("/")
def index():
    return render_template("whatsapp_simulator.html", messages=service.get_messages())


@app.route("/api/messages", methods=["GET"])
def get_messages():
    return jsonify({"messages": service.get_messages()})


@app.route("/api/messages", methods=["POST"])
def post_message():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if text:
        service.add_message("Usuario", text)
        context = ""
        normalized_text = text.casefold()
        spam_terms = ("spam", "correo no deseado", "correos no deseados", "correo basura", "correos basura")
        unread_terms = ("sin leer", "no leído", "no leídos", "no leida", "no leidas", "unread")
        mail_terms = ("correo", "correos", "bandeja", "email", "e-mail", "inbox")
        if any(term in normalized_text for term in spam_terms):
            try:
                spam_count = GmailService().get_spam_count()
                if spam_count is None:
                    answer = "No puedo contar el spam porque Gmail no está conectado en modo real."
                else:
                    noun = "correo" if spam_count == 1 else "correos"
                    answer = f"Gmail muestra {spam_count} {noun} en la carpeta Spam."
            except Exception:
                app.logger.exception("No se pudo consultar la carpeta Spam de Gmail")
                answer = "No pude consultar la carpeta Spam de Gmail. Revisa la conexión o los permisos de Gmail e inténtalo de nuevo."
        elif any(term in normalized_text for term in unread_terms):
            try:
                unread_count = GmailService().get_unread_count()
                if unread_count is None:
                    answer = "No puedo contar los correos sin leer porque Gmail no está conectado en modo real."
                else:
                    noun = "correo sin leer" if unread_count == 1 else "correos sin leer"
                    answer = f"Tienes {unread_count} {noun} en la bandeja de entrada."
            except Exception:
                app.logger.exception("No se pudo consultar los correos sin leer de Gmail")
                answer = "No pude consultar los correos sin leer de Gmail. Revisa la conexión o los permisos de Gmail e inténtalo de nuevo."
        else:
            if any(term in normalized_text for term in mail_terms):
                try:
                    emails = GmailService().get_messages(max_results=3)
                    context = "\n\n".join(
                        f"Asunto: {email.get('subject', 'Sin asunto')}\n"
                        f"De: {email.get('from', 'Remitente desconocido')}\n"
                        f"Contenido: {str(email.get('body', ''))[:1200]}"
                        for email in emails
                    ) or "No se encontraron correos en la bandeja de entrada."
                except Exception:
                    context = "No se pudo consultar Gmail en este momento."

            try:
                answer = LLMService().respond_to_chat(text, context)
            except Exception:
                app.logger.exception("No se pudo generar una respuesta para el chat")
                answer = "No pude consultar la IA ahora. Revisa la conexión y la configuración de tu API, e inténtalo de nuevo."
        service.add_message("Agente", answer)
    return jsonify({"messages": service.get_messages()})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
