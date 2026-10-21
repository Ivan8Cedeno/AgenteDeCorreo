from __future__ import annotations

from typing import Any, Dict, Optional

from app.gmail_service import GmailService
from app.llm_service import LLMService
from app.whatsapp_service import WhatsAppService


SPAM_KEYWORDS = [
    "click here",
    "winner",
    "claim prize",
    "verify your account",
    "urgent!!!",
    "free money",
    "limited time",
    "lottery",
    "cash",
    "click now",
]

URGENT_KEYWORDS = [
    "urgente",
    "critical",
    "deadline",
    "hoy mismo",
    "vence esta tarde",
    "asap",
    "critical customer",
    "pedido crítico",
    "pago pendiente",
    "respuesta hoy",
]


class MailAgent:
    def __init__(self, gmail_service: Optional[GmailService] = None):
        self.gmail_service = gmail_service or GmailService()
        self.llm_service = LLMService()
        self.whatsapp_service = WhatsAppService()

    def classify_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        subject = str(message.get("subject", "")).lower()
        body = str(message.get("body", "")).lower()
        text = f"{subject} {body}"

        if any(keyword in text for keyword in SPAM_KEYWORDS):
            return {
                "id": message.get("id", ""),
                "action": "spam",
                "priority": "low",
                "summary": "Correo sospechoso identificado como spam.",
                "needs_whatsapp": False,
                "draft": {"subject": "Sin respuesta", "body": "Este mensaje se marcó como spam."},
            }

        if any(keyword in text for keyword in URGENT_KEYWORDS):
            summary = self.llm_service.summarize(message)
            draft = self.llm_service.build_reply(message, "draft")
            draft["subject"] = f"RE: {draft['subject']}"
            return {
                "id": message.get("id", ""),
                "action": "draft",
                "priority": "critical" if "urgente" in text or "critical" in text else "high",
                "summary": summary,
                "needs_whatsapp": True,
                "draft": draft,
            }

        summary = self.llm_service.summarize(message)
        draft = self.llm_service.build_reply(message, "draft")
        return {
            "id": message.get("id", ""),
            "action": "draft",
            "priority": "normal",
            "summary": summary,
            "needs_whatsapp": False,
            "draft": draft,
        }

    def process_inbox(self, max_results: int = 5) -> list[Dict[str, Any]]:
        results = []
        for message in self.gmail_service.get_messages(max_results=max_results):
            decision = self.classify_message(message)
            results.append(decision)

            if decision["action"] == "draft":
                response = self.gmail_service.create_draft(
                    subject=decision["draft"]["subject"],
                    body=decision["draft"]["body"],
                )
                decision["draft_status"] = response

            if decision.get("needs_whatsapp"):
                decision["whatsapp_status"] = self.whatsapp_service.send_alert(
                    subject=message.get("subject", "Correo urgente"),
                    summary=decision["summary"],
                )

        return results
