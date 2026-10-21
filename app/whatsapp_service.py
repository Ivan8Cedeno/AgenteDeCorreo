from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings


class WhatsAppService:
    _shared_messages: List[Dict[str, str]] = []

    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_from
        self.to_number = settings.twilio_to
        self.messages = self._shared_messages

    def get_messages(self) -> List[Dict[str, str]]:
        return self.messages

    def add_message(self, sender: str, text: str) -> None:
        self.messages.append({"sender": sender, "text": text})

    def send_alert(self, subject: str, summary: str) -> str:
        simulated_message = f"Correo urgente: {subject} - {summary[:160]}"
        self.add_message("Agente", simulated_message)

        if not self.account_sid or not self.auth_token or not self.from_number or not self.to_number:
            return f"WhatsApp simulado: {subject} - {summary[:120]}"

        try:
            from twilio.rest import Client

            client = Client(self.account_sid, self.auth_token)
            message = client.messages.create(
                body=f"Correo urgente: {subject}\n{summary}",
                from_=self.from_number,
                to=self.to_number,
            )
            return f"Mensaje enviado: {message.sid}"
        except Exception as exc:  # pragma: no cover - critical integration branch
            return f"Error al enviar WhatsApp: {exc}"
