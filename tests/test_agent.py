from app.agent import MailAgent
from app.gmail_service import GmailService


class DummySendResponse:
    def execute(self):
        return {"id": "sent-123"}


class DummyMessages:
    def __init__(self):
        self.calls = []

    def send(self, userId, body):
        self.calls.append({"userId": userId, "body": body})
        return DummySendResponse()


class DummyProfile:
    def execute(self):
        return {"emailAddress": "test@gmail.com"}


class DummyUsers:
    def __init__(self):
        self.messages_obj = DummyMessages()
        self.profile = DummyProfile()

    def messages(self):
        return self.messages_obj

    def getProfile(self, userId):
        return self.profile

    def users(self):
        return self


class DummyListRequest:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def execute(self):
        return self.response


class DummySpamMessages:
    def __init__(self):
        self.responses = [
            {"messages": [{"id": "spam-1"}, {"id": "spam-2"}], "nextPageToken": "page-2"},
            {"messages": [{"id": "spam-3"}]},
        ]
        self.requests = []

    def list(self, **kwargs):
        request = DummyListRequest(self.responses[len(self.requests)])
        request.kwargs = kwargs
        self.requests.append(request)
        return request


class DummySpamUsers:
    def __init__(self):
        self.messages_obj = DummySpamMessages()

    def messages(self):
        return self.messages_obj

    def users(self):
        return self


class DummyUnreadUsers:
    def __init__(self):
        self.messages_obj = DummySpamMessages()
        self.messages_obj.responses = [
            {"messages": [{"id": "unread-1"}], "nextPageToken": "unread-page-2"},
            {"messages": [{"id": "unread-2"}, {"id": "unread-3"}]},
        ]

    def messages(self):
        return self.messages_obj

    def users(self):
        return self


def test_gmail_create_draft_uses_raw_payload():
    gmail = GmailService(demo_mode=False)
    gmail.service = DummyUsers()

    result = gmail.create_draft("Prueba", "Hola mundo")

    assert result == "Borrador creado para: Prueba"
    payload = gmail.service.messages_obj.calls[0]["body"]
    raw_data = payload["raw"]
    decoded = __import__("base64").urlsafe_b64decode(raw_data + "=" * (-len(raw_data) % 4)).decode("utf-8")
    assert "To: test@gmail.com" in decoded
    assert "From: test@gmail.com" in decoded
    assert "message" not in payload


def test_gmail_counts_all_pages_of_spam_messages():
    gmail = GmailService(demo_mode=False)
    gmail.service = DummySpamUsers()

    assert gmail.get_spam_count() == 3
    first_request = gmail.service.messages_obj.requests[0]
    assert first_request.kwargs["labelIds"] == ["SPAM"]
    assert first_request.kwargs["includeSpamTrash"] is True
    assert gmail.service.messages_obj.requests[1].kwargs["pageToken"] == "page-2"


def test_gmail_counts_all_pages_of_unread_inbox_messages():
    gmail = GmailService(demo_mode=False)
    gmail.service = DummyUnreadUsers()

    assert gmail.get_unread_count() == 3
    first_request = gmail.service.messages_obj.requests[0]
    assert first_request.kwargs["labelIds"] == ["INBOX", "UNREAD"]
    assert gmail.service.messages_obj.requests[1].kwargs["pageToken"] == "unread-page-2"


def test_marks_scam_email_as_spam():
    agent = MailAgent()
    message = {
        "id": "1",
        "subject": "URGENT!!! You won a prize",
        "from": "winner@fake-domain.com",
        "body": "Click here now to claim your reward and verify your account.",
    }

    result = agent.classify_message(message)

    assert result["action"] == "spam"
    assert result["needs_whatsapp"] is False


def test_marks_urgent_email_for_summary_and_notification():
    agent = MailAgent()
    message = {
        "id": "2",
        "subject": "Pedido crítico de cliente",
        "from": "cliente@empresa.com",
        "body": "Necesitamos una respuesta hoy mismo sobre el presupuesto del proyecto. El plazo se vence esta tarde.",
    }

    result = agent.classify_message(message)

    assert result["action"] == "draft"
    assert result["priority"] in {"high", "critical"}
    assert result["needs_whatsapp"] is True
