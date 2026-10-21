import base64
import os
import sys
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import BASE_DIR, settings


class GmailService:
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    def __init__(self, demo_mode: Optional[bool] = None):
        self.demo_mode = settings.demo_mode if demo_mode is None else demo_mode
        self.service = self._connect_service() if not self.demo_mode else None

    def _connect_service(self):
        credentials_path = Path(settings.gmail_credentials_path)
        token_path = Path(settings.gmail_token_path)
        if not credentials_path.is_absolute():
            credentials_path = BASE_DIR / credentials_path
        if not token_path.is_absolute():
            token_path = BASE_DIR / token_path

        if not credentials_path.exists():
            return None

        if not token_path.exists() and not sys.stdin.isatty():
            return None

        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        if not creds or not creds.valid or not creds.has_scopes(self.SCOPES):
            if creds and creds.expired and creds.refresh_token:
                if not creds.valid:
                    raise RuntimeError("No se pudo renovar la autorización de Gmail.")
            elif not sys.stdin.isatty():
                return None
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), self.SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True)
                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text(creds.to_json(), encoding="utf-8")

        return build("gmail", "v1", credentials=creds)

    def get_messages(self, max_results: int = 5) -> List[Dict[str, Any]]:
        if self.demo_mode:
            return self._demo_messages()

        if self.service is None:
            raise RuntimeError("Gmail no está conectado; no se procesaron mensajes de ejemplo.")

        result = self.service.users().messages().list(
            userId="me",
            q="in:inbox",
            maxResults=max_results,
        ).execute()
        messages = result.get("messages", [])
        items: List[Dict[str, Any]] = []
        for item in messages:
            msg = self.service.users().messages().get(userId="me", id=item["id"], format="full").execute()
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "Sin asunto")
            sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "Remitente desconocido")
            body = self._extract_body(payload)
            items.append(
                {
                    "id": msg["id"],
                    "thread_id": msg.get("threadId"),
                    "message_id": next(
                        (h["value"] for h in headers if h["name"].lower() == "message-id"),
                        None,
                    ),
                    "references": next(
                        (h["value"] for h in headers if h["name"].lower() == "references"),
                        None,
                    ),
                    "subject": subject,
                    "from": sender,
                    "body": body,
                }
            )
        return items

    def get_spam_count(self) -> Optional[int]:
        """Return the exact number of messages in Gmail's Spam label, or None if unavailable."""
        if self.demo_mode or self.service is None:
            return None

        count = 0
        page_token = None
        while True:
            result = self.service.users().messages().list(
                userId="me",
                labelIds=["SPAM"],
                includeSpamTrash=True,
                maxResults=500,
                pageToken=page_token,
            ).execute()
            count += len(result.get("messages", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                return count

    def get_unread_count(self) -> Optional[int]:
        """Return the exact unread inbox count, or None if Gmail is unavailable."""
        if self.demo_mode or self.service is None:
            return None

        count = 0
        page_token = None
        while True:
            result = self.service.users().messages().list(
                userId="me",
                labelIds=["INBOX", "UNREAD"],
                maxResults=500,
                pageToken=page_token,
            ).execute()
            count += len(result.get("messages", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                return count

    def mark_unread_inbox_as_read(self) -> int:
        """Mark every currently unread inbox message as read and return its count."""
        if self.demo_mode:
            raise RuntimeError("La acción de marcar correos requiere Gmail en modo real.")
        if self.service is None:
            raise RuntimeError("Gmail no está conectado; no se modificaron correos.")

        message_ids = []
        page_token = None
        while True:
            result = self.service.users().messages().list(
                userId="me",
                labelIds=["INBOX", "UNREAD"],
                maxResults=500,
                pageToken=page_token,
            ).execute()
            message_ids.extend(item["id"] for item in result.get("messages", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        for start in range(0, len(message_ids), 1000):
            self.service.users().messages().batchModify(
                userId="me",
                body={
                    "ids": message_ids[start : start + 1000],
                    "removeLabelIds": ["UNREAD"],
                },
            ).execute()

        return len(message_ids)

    def star_message(self, message_id: str) -> str:
        if self.demo_mode:
            raise RuntimeError("La acción de destacar correos requiere Gmail en modo real.")
        if self.service is None:
            raise RuntimeError("Gmail no está conectado; no se destacó ningún correo.")

        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": ["STARRED"]},
        ).execute()
        return "Correo destacado con una estrella."

    @staticmethod
    def _extract_body(payload: Dict[str, Any]) -> str:
        if payload.get("mimeType", "").startswith("multipart/"):
            for part in payload.get("parts", []):
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data")
                    if data:
                        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="ignore")
        body_data = payload.get("body", {}).get("data")
        if body_data:
            return base64.urlsafe_b64decode(body_data + "=" * (-len(body_data) % 4)).decode("utf-8", errors="ignore")
        return ""

    @staticmethod
    def _demo_messages() -> List[Dict[str, Any]]:
        return [
            {
                "id": "demo-1",
                "subject": "URGENT!!! You won a prize",
                "from": "winner@fake-domain.com",
                "body": "Click here now to claim your reward and verify your account.",
            },
            {
                "id": "demo-2",
                "subject": "Pedido crítico de cliente",
                "from": "cliente@empresa.com",
                "body": "Necesitamos una respuesta hoy mismo sobre el presupuesto del proyecto. El plazo se vence esta tarde.",
            },
            {
                "id": "demo-3",
                "subject": "Reunión del equipo",
                "from": "colega@empresa.com",
                "body": "Te confirmo la reunión para mañana a las 10:00 y la agenda está adjunta.",
            },
        ]

    def create_draft(self, subject: str, body: str) -> str:
        return self.create_reply_draft(subject=subject, body=body)

    def create_reply_draft(
        self,
        subject: str,
        body: str,
        recipient: str = "",
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        references: Optional[str] = None,
    ) -> str:
        if self.demo_mode:
            return f"Borrador de prueba creado: {subject}"

        if self.service is None:
            raise RuntimeError("Gmail no está conectado; no se pudo guardar el borrador.")

        profile = self.service.users().getProfile(userId="me").execute()
        account_email = profile.get("emailAddress")
        if not account_email:
            raise RuntimeError("Gmail no devolvió la dirección de la cuenta autorizada.")

        message = EmailMessage()
        if recipient:
            message["To"] = recipient
        message["From"] = account_email
        message["Subject"] = subject
        if message_id:
            message["In-Reply-To"] = message_id
            message["References"] = " ".join(filter(None, [references, message_id]))
        message.set_content(body)

        draft_message = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")}
        if thread_id:
            draft_message["threadId"] = thread_id
        self.service.users().drafts().create(
            userId="me",
            body={"message": draft_message},
        ).execute()
        return f"Borrador creado para: {subject}"

    def mark_as_spam(self, message_id: str) -> str:
        if self.demo_mode:
            return "Correo de prueba marcado como spam."

        if self.service is None:
            raise RuntimeError("Gmail no está conectado; no se pudo mover el correo a Spam.")

        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]},
        ).execute()
        return "Correo movido a Spam."
