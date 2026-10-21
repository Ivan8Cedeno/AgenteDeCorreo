from __future__ import annotations

import os
import re
import sys
import unicodedata
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
pending_confirmation: dict[str, str] | None = None


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _requests_mark_as_read(text: str) -> bool:
    normalized = _normalize_text(text)
    asks_to_mark = re.search(r"\bmarc(?:a|ar|ame|alos|arlas)\b", normalized)
    mentions_read = re.search(r"\bleid[oa]s?\b", normalized)
    return bool(asks_to_mark and mentions_read)


def _extract_star_target(text: str) -> str | None:
    normalized = _normalize_text(text)
    match = re.search(r"\b(?:destaca(?:r|me)?|pon(?:le)?\s+(?:una\s+)?estrella)\b", normalized)
    if not match:
        return None

    target = normalized[match.end() :].strip(" \t\r\n.!¡?¿,;:")
    target = re.sub(r"^(?:(?:el|la|los|las)\s+)?(?:correo|email|mensaje)\b", "", target).strip()
    target = re.sub(r"^(?:de|del|con asunto|asunto|sobre)\s+", "", target).strip()
    return target or None


def _confirms_pending_action(text: str) -> bool:
    normalized = _normalize_text(text).strip(" \t\r\n.!¡?¿")
    return normalized in {
        "si",
        "si, confirmo",
        "confirmo",
        "confirmar",
        "si, marca todos como leidos",
        "si, marcar como leidos",
        "adelante",
        "hazlo",
    }


@app.route("/")
def index():
    return render_template("whatsapp_simulator.html", messages=service.get_messages())


@app.route("/api/messages", methods=["GET"])
def get_messages():
    return jsonify({"messages": service.get_messages()})


@app.route("/api/messages", methods=["POST"])
def post_message():
    global pending_confirmation

    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if text:
        service.add_message("Usuario", text)
        context = ""
        normalized_text = _normalize_text(text)
        spam_terms = ("spam", "correo no deseado", "correos no deseados", "correo basura", "correos basura")
        unread_terms = ("sin leer", "no leido", "no leidos", "no leida", "no leidas", "unread")
        mail_terms = ("correo", "correos", "bandeja", "email", "e-mail", "inbox")

        if pending_confirmation and _confirms_pending_action(text):
            confirmed_action = pending_confirmation
            pending_confirmation = None
            try:
                gmail = GmailService()
                if confirmed_action["type"] == "mark_read":
                    marked_count = gmail.mark_unread_inbox_as_read()
                    answer = f"Listo. Marqué {marked_count} correos como leídos en la bandeja de entrada."
                else:
                    answer = gmail.star_message(confirmed_action["id"])
            except Exception:
                app.logger.exception("No se pudo completar la acción confirmada de Gmail")
                answer = "No pude completar la acción en Gmail. Revisa la conexión o los permisos e inténtalo de nuevo."
        elif pending_confirmation and normalized_text in {"no", "no, cancelar", "cancelar", "cancela"}:
            pending_confirmation = None
            answer = "De acuerdo, no cambié el estado de ningún correo."
        else:
            if pending_confirmation:
                pending_confirmation = None

            star_target = _extract_star_target(text)
            if star_target:
                try:
                    emails = GmailService().get_messages(max_results=50)
                    matches = [
                        email
                        for email in emails
                        if star_target in _normalize_text(email.get("subject", ""))
                        or star_target in _normalize_text(email.get("from", ""))
                    ]
                    if not matches:
                        answer = (
                            "No encontré correos recientes de la bandeja cuyo asunto o remitente coincida. "
                            "Prueba con una parte más específica del asunto o el remitente."
                        )
                    elif len(matches) > 1:
                        candidates = "; ".join(
                            f"«{email.get('subject', 'Sin asunto')}» ({email.get('from', 'Remitente desconocido')})"
                            for email in matches[:5]
                        )
                        answer = (
                            f"Encontré {len(matches)} correos coincidentes: {candidates}. "
                            "Indica un asunto o remitente más específico."
                        )
                    else:
                        email = matches[0]
                        pending_confirmation = {
                            "type": "star",
                            "id": email["id"],
                            "subject": email.get("subject", "Sin asunto"),
                        }
                        answer = (
                            f"Encontré «{email.get('subject', 'Sin asunto')}» de "
                            f"{email.get('from', 'Remitente desconocido')}. "
                            "¿Confirmas que le ponga una estrella? Responde «sí» o «cancelar»."
                        )
                except Exception:
                    app.logger.exception("No se pudo buscar el correo que se quiere destacar")
                    answer = "No pude buscar ese correo en Gmail. Revisa la conexión o los permisos e inténtalo de nuevo."
            elif _requests_mark_as_read(text):
                try:
                    unread_count = GmailService().get_unread_count()
                    if unread_count is None:
                        answer = "No puedo modificar la bandeja porque Gmail no está conectado en modo real."
                    elif unread_count == 0:
                        answer = "No hay correos sin leer en la bandeja de entrada."
                    else:
                        pending_confirmation = {"type": "mark_read"}
                        noun = "correo" if unread_count == 1 else "correos"
                        answer = (
                            f"Tienes {unread_count} {noun} sin leer en la bandeja de entrada. "
                            "¿Confirmas que los marque todos como leídos? Responde «sí» para confirmar o «cancelar»."
                        )
                except Exception:
                    app.logger.exception("No se pudo consultar los correos sin leer de Gmail")
                    answer = "No pude consultar la bandeja. Revisa la conexión o los permisos de Gmail e inténtalo de nuevo."
            elif any(term in normalized_text for term in spam_terms):
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
