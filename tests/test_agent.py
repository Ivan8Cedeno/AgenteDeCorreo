from app.agent import MailAgent
from app.gmail_service import GmailService
from app.llm_service import LLMService


class DummySendResponse:
    def execute(self):
        return {"id": "sent-123"}


class DummyMessages:
    def __init__(self):
        self.modify_calls = []

    def modify(self, **kwargs):
        self.modify_calls.append(kwargs)
        return DummySendResponse()


class DummyDrafts:
    def __init__(self):
        self.calls = []

    def create(self, userId, body):
        self.calls.append({"userId": userId, "body": body})
        return DummySendResponse()


class DummyProfile:
    def execute(self):
        return {"emailAddress": "test@gmail.com"}


class DummyUsers:
    def __init__(self):
        self.messages_obj = DummyMessages()
        self.drafts_obj = DummyDrafts()
        self.profile = DummyProfile()

    def messages(self):
        return self.messages_obj

    def drafts(self):
        return self.drafts_obj

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


class DummyBatchMessages:
    def __init__(self, responses):
        self.responses = responses
        self.list_requests = []
        self.batch_requests = []

    def list(self, **kwargs):
        request = DummyListRequest(self.responses[len(self.list_requests)])
        request.kwargs = kwargs
        self.list_requests.append(request)
        return request

    def batchModify(self, **kwargs):
        request = DummyListRequest({})
        request.kwargs = kwargs
        self.batch_requests.append(request)
        return request


class DummyBatchUsers:
    def __init__(self, responses):
        self.messages_obj = DummyBatchMessages(responses)

    def messages(self):
        return self.messages_obj

    def users(self):
        return self


def test_gmail_reads_only_inbox_messages():
    class InboxMessages:
        def __init__(self):
            self.list_kwargs = None

        def list(self, **kwargs):
            self.list_kwargs = kwargs
            return DummyListRequest({"messages": [{"id": "inbox-1"}]})

        def get(self, **kwargs):
            return DummyListRequest(
                {
                    "id": "inbox-1",
                    "threadId": "thread-1",
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": "Hola"},
                            {"name": "From", "value": "Ana <ana@example.com>"},
                        ],
                        "body": {"data": "SG9sYQ"},
                    },
                }
            )

    class InboxUsers:
        def __init__(self):
            self.messages_obj = InboxMessages()

        def messages(self):
            return self.messages_obj

        def users(self):
            return self

    gmail = GmailService(demo_mode=True)
    gmail.demo_mode = False
    gmail.service = InboxUsers()

    messages = gmail.get_messages(max_results=1)

    assert gmail.service.messages_obj.list_kwargs["q"] == "in:inbox"
    assert messages[0]["thread_id"] == "thread-1"
    assert messages[0]["from"] == "Ana <ana@example.com>"
    assert messages[0]["body"] == "Hola"


def test_gmail_marks_all_unread_inbox_messages_read_in_batches():
    pages = [
        {
            "messages": [{"id": f"message-{index}"} for index in range(500)],
            "nextPageToken": "page-2",
        },
        {
            "messages": [{"id": f"message-{index}"} for index in range(500, 1000)],
            "nextPageToken": "page-3",
        },
        {"messages": [{"id": "message-1000"}]},
    ]
    gmail = GmailService(demo_mode=True)
    gmail.demo_mode = False
    gmail.service = DummyBatchUsers(pages)

    assert gmail.mark_unread_inbox_as_read() == 1001

    messages = gmail.service.messages_obj
    assert len(messages.list_requests) == 3
    assert messages.list_requests[0].kwargs["labelIds"] == ["INBOX", "UNREAD"]
    assert messages.list_requests[1].kwargs["pageToken"] == "page-2"
    assert messages.list_requests[2].kwargs["pageToken"] == "page-3"
    assert [len(call.kwargs["body"]["ids"]) for call in messages.batch_requests] == [1000, 1]
    assert messages.batch_requests[0].kwargs["body"]["removeLabelIds"] == ["UNREAD"]
    assert messages.batch_requests[1].kwargs["body"]["ids"] == ["message-1000"]


def test_gmail_create_draft_uses_raw_payload():
    gmail = GmailService(demo_mode=True)
    gmail.demo_mode = False
    gmail.service = DummyUsers()

    result = gmail.create_reply_draft(
        "Re: Prueba",
        "Hola mundo",
        recipient="remitente@example.com",
        thread_id="thread-123",
        message_id="<message-123@example.com>",
    )

    assert result == "Borrador creado para: Re: Prueba"
    payload = gmail.service.drafts_obj.calls[0]["body"]["message"]
    raw_data = payload["raw"]
    decoded = __import__("base64").urlsafe_b64decode(raw_data + "=" * (-len(raw_data) % 4)).decode("utf-8")
    assert "To: remitente@example.com" in decoded
    assert "From: test@gmail.com" in decoded
    assert "In-Reply-To: <message-123@example.com>" in decoded
    assert payload["threadId"] == "thread-123"


def test_gmail_marks_message_as_spam_without_sending_it():
    gmail = GmailService(demo_mode=True)
    gmail.demo_mode = False
    gmail.service = DummyUsers()

    result = gmail.mark_as_spam("message-123")

    assert result == "Correo movido a Spam."
    assert gmail.service.messages_obj.modify_calls == [
        {
            "userId": "me",
            "id": "message-123",
            "body": {"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]},
        }
    ]


def test_gmail_stars_the_requested_message_without_removing_other_labels():
    gmail = GmailService(demo_mode=True)
    gmail.demo_mode = False
    gmail.service = DummyUsers()

    result = gmail.star_message("message-123")

    assert result == "Correo destacado con una estrella."
    assert gmail.service.messages_obj.modify_calls == [
        {
            "userId": "me",
            "id": "message-123",
            "body": {"addLabelIds": ["STARRED"]},
        }
    ]


def test_process_inbox_moves_spam_and_creates_reply_draft():
    class FakeGmail:
        def __init__(self):
            self.spam_ids = []
            self.drafts = []

        def get_messages(self, max_results):
            return [
                {
                    "id": "spam-1",
                    "subject": "Winner",
                    "from": "promo@example.com",
                    "body": "Click here to claim prize",
                },
                {
                    "id": "urgent-1",
                    "subject": "Pedido crítico",
                    "from": "cliente@example.com",
                    "body": "Necesito respuesta hoy mismo",
                    "thread_id": "thread-urgent",
                },
            ]

        def mark_as_spam(self, message_id):
            self.spam_ids.append(message_id)
            return "Correo movido a Spam."

        def create_reply_draft(self, **kwargs):
            self.drafts.append(kwargs)
            return "Borrador creado."

    gmail = FakeGmail()
    agent = MailAgent(gmail_service=gmail)

    decisions = agent.process_inbox(max_results=2)

    assert gmail.spam_ids == ["spam-1"]
    assert gmail.drafts[0]["recipient"] == "cliente@example.com"
    assert gmail.drafts[0]["thread_id"] == "thread-urgent"
    assert decisions[0]["spam_status"] == "Correo movido a Spam."
    assert decisions[1]["draft_status"] == "Borrador creado."


def test_gmail_counts_all_pages_of_spam_messages():
    gmail = GmailService(demo_mode=True)
    gmail.demo_mode = False
    gmail.service = DummySpamUsers()

    assert gmail.get_spam_count() == 3
    first_request = gmail.service.messages_obj.requests[0]
    assert first_request.kwargs["labelIds"] == ["SPAM"]
    assert first_request.kwargs["includeSpamTrash"] is True
    assert gmail.service.messages_obj.requests[1].kwargs["pageToken"] == "page-2"


def test_gmail_counts_all_pages_of_unread_inbox_messages():
    gmail = GmailService(demo_mode=True)
    gmail.demo_mode = False
    gmail.service = DummyUnreadUsers()

    assert gmail.get_unread_count() == 3
    first_request = gmail.service.messages_obj.requests[0]
    assert first_request.kwargs["labelIds"] == ["INBOX", "UNREAD"]
    assert gmail.service.messages_obj.requests[1].kwargs["pageToken"] == "unread-page-2"


def test_marks_scam_email_as_spam():
    agent = MailAgent(gmail_service=GmailService(demo_mode=True))
    message = {
        "id": "1",
        "subject": "URGENT!!! You won a prize",
        "from": "winner@fake-domain.com",
        "body": "Click here now to claim your reward and verify your account.",
    }

    result = agent.classify_message(message)

    assert result["action"] == "spam"
    assert result["needs_whatsapp"] is False


def test_reply_draft_normalizes_existing_reply_prefixes():
    draft = LLMService().build_reply(
        {"subject": "Re: RE: Fwd: Pedido", "from": "ana@example.com"},
        "draft",
    )

    assert draft["subject"] == "Re: Pedido"
    assert draft["body"].startswith("Hola,")


def test_marks_urgent_email_for_summary_and_notification():
    agent = MailAgent(gmail_service=GmailService(demo_mode=True))
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
