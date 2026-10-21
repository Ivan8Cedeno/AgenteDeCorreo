from app import web_app


def test_chat_returns_agent_reply(monkeypatch):
    web_app.service.messages.clear()

    class FakeLLMService:
        def respond_to_chat(self, prompt, context=""):
            return f"Respuesta de prueba: {prompt}"

    monkeypatch.setattr(web_app, "LLMService", FakeLLMService)
    response = web_app.app.test_client().post("/api/messages", json={"text": "Hola"})

    assert response.status_code == 200
    messages = response.get_json()["messages"]
    assert messages[-2] == {"sender": "Usuario", "text": "Hola"}
    assert messages[-1] == {"sender": "Agente", "text": "Respuesta de prueba: Hola"}


def test_chat_reports_gmail_spam_count_without_calling_llm(monkeypatch):
    web_app.service.messages.clear()

    class FakeGmailService:
        def get_spam_count(self):
            return 7

    class UnexpectedLLMService:
        def __init__(self):
            raise AssertionError("La consulta de conteo no necesita llamar a la IA")

    monkeypatch.setattr(web_app, "GmailService", FakeGmailService)
    monkeypatch.setattr(web_app, "LLMService", UnexpectedLLMService)
    response = web_app.app.test_client().post(
        "/api/messages", json={"text": "¿Cuántos correos tengo en spam?"}
    )

    assert response.status_code == 200
    messages = response.get_json()["messages"]
    assert messages[-1] == {"sender": "Agente", "text": "Gmail muestra 7 correos en la carpeta Spam."}


def test_chat_reports_unread_gmail_count_without_calling_llm(monkeypatch):
    web_app.service.messages.clear()

    class FakeGmailService:
        def get_unread_count(self):
            return 4

    class UnexpectedLLMService:
        def __init__(self):
            raise AssertionError("La consulta de conteo no necesita llamar a la IA")

    monkeypatch.setattr(web_app, "GmailService", FakeGmailService)
    monkeypatch.setattr(web_app, "LLMService", UnexpectedLLMService)
    response = web_app.app.test_client().post(
        "/api/messages", json={"text": "¿Cuántos correos tengo sin leer?"}
    )

    assert response.status_code == 200
    messages = response.get_json()["messages"]
    assert messages[-1] == {
        "sender": "Agente",
        "text": "Tienes 4 correos sin leer en la bandeja de entrada.",
    }


def test_marking_inbox_as_read_requires_confirmation(monkeypatch):
    web_app.service.messages.clear()
    monkeypatch.setattr(web_app, "pending_confirmation", None)
    calls = []

    class FakeGmailService:
        def get_unread_count(self):
            return 4

        def mark_unread_inbox_as_read(self):
            calls.append("marked")
            return 4

    class UnexpectedLLMService:
        def __init__(self):
            raise AssertionError("La acción de marcar no necesita llamar a la IA")

    monkeypatch.setattr(web_app, "GmailService", FakeGmailService)
    monkeypatch.setattr(web_app, "LLMService", UnexpectedLLMService)
    client = web_app.app.test_client()

    response = client.post(
        "/api/messages",
        json={"text": "Marca como leídos todos los correos de mi bandeja"},
    )

    assert response.status_code == 200
    assert "Tienes 4 correos" in response.get_json()["messages"][-1]["text"]
    assert calls == []

    response = client.post("/api/messages", json={"text": "sí"})

    assert response.status_code == 200
    assert response.get_json()["messages"][-1]["text"] == (
        "Listo. Marqué 4 correos como leídos en la bandeja de entrada."
    )
    assert calls == ["marked"]


def test_canceling_mark_as_read_does_not_change_gmail(monkeypatch):
    web_app.service.messages.clear()
    monkeypatch.setattr(web_app, "pending_confirmation", None)
    calls = []

    class FakeGmailService:
        def get_unread_count(self):
            return 2

        def mark_unread_inbox_as_read(self):
            calls.append("marked")
            return 2

    monkeypatch.setattr(web_app, "GmailService", FakeGmailService)
    client = web_app.app.test_client()
    client.post(
        "/api/messages",
        json={"text": "Marca como leídos todos los correos de mi bandeja"},
    )
    response = client.post("/api/messages", json={"text": "cancelar"})

    assert response.get_json()["messages"][-1]["text"] == (
        "De acuerdo, no cambié el estado de ningún correo."
    )
    assert calls == []


def test_starring_a_matching_email_requires_confirmation(monkeypatch):
    web_app.service.messages.clear()
    monkeypatch.setattr(web_app, "pending_confirmation", None)
    calls = []

    class FakeGmailService:
        def get_messages(self, max_results):
            assert max_results == 50
            return [
                {
                    "id": "mail-123",
                    "subject": "Factura de abril",
                    "from": "Ana <ana@example.com>",
                }
            ]

        def star_message(self, message_id):
            calls.append(message_id)
            return "Correo destacado con una estrella."

    class UnexpectedLLMService:
        def __init__(self):
            raise AssertionError("Destacar un correo no necesita llamar a la IA")

    monkeypatch.setattr(web_app, "GmailService", FakeGmailService)
    monkeypatch.setattr(web_app, "LLMService", UnexpectedLLMService)
    client = web_app.app.test_client()

    response = client.post("/api/messages", json={"text": "Destaca el correo de Ana"})

    assert response.status_code == 200
    assert "¿Confirmas que le ponga una estrella?" in response.get_json()["messages"][-1]["text"]
    assert calls == []

    response = client.post("/api/messages", json={"text": "sí"})

    assert response.status_code == 200
    assert response.get_json()["messages"][-1]["text"] == "Correo destacado con una estrella."
    assert calls == ["mail-123"]


def test_starring_requires_a_unique_email_match(monkeypatch):
    web_app.service.messages.clear()
    monkeypatch.setattr(web_app, "pending_confirmation", None)

    class FakeGmailService:
        def get_messages(self, max_results):
            return [
                {"id": "mail-1", "subject": "Factura abril", "from": "Ana <ana@example.com>"},
                {"id": "mail-2", "subject": "Factura mayo", "from": "Ana <ana@example.com>"},
            ]

        def star_message(self, message_id):
            raise AssertionError("No se debe destacar si hay varios resultados")

    monkeypatch.setattr(web_app, "GmailService", FakeGmailService)
    response = web_app.app.test_client().post(
        "/api/messages",
        json={"text": "Destaca el correo de Ana"},
    )

    assert "Encontré 2 correos coincidentes" in response.get_json()["messages"][-1]["text"]