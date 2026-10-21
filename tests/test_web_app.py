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