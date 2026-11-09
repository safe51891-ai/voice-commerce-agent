from fastapi.testclient import TestClient

from app import main
from app.tools import LEADS


def fake_llm(messages, tools):
    return {"role": "assistant", "content": "Our current offers include WINTER15."}


def client_with_fake_llm(monkeypatch):
    monkeypatch.setattr(main, "get_llm", lambda: fake_llm)
    return TestClient(main.app)


def test_index_serves_chat_page():
    response = TestClient(main.app).get("/")
    assert response.status_code == 200
    assert "voice agent test" in response.text


def test_chat_returns_reply(monkeypatch):
    client = client_with_fake_llm(monkeypatch)
    response = client.post("/api/chat", json={"session_id": "s1", "message": "any deals?"})
    assert response.status_code == 200
    assert "WINTER15" in response.json()["reply"]


def test_chat_without_key_returns_503(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = TestClient(main.app).post("/api/chat", json={"session_id": "s2", "message": "hello"})
    assert response.status_code == 503


def test_leads_refused_without_admin_token(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert TestClient(main.app).get("/api/leads").status_code == 403


def test_leads_visible_with_admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    LEADS.clear()
    client = TestClient(main.app)
    assert client.get("/api/leads", headers={"Authorization": "Bearer wrong"}).status_code == 403
    assert client.get("/api/leads", headers={"Authorization": "Bearer secret-token"}).json() == []


def test_twilio_voice_returns_greeting_and_gather(monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.ngrok.app")
    response = TestClient(main.app).post("/twilio/voice")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<Say>Thanks for calling Northwind Outfitters" in response.text
    assert 'action="https://example.ngrok.app/twilio/turn"' in response.text


def test_twilio_turn_with_empty_speech_asks_again(monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    response = TestClient(main.app).post("/twilio/turn", data={"CallSid": "CA1", "SpeechResult": ""})
    assert "didn&apos;t catch that" in response.text or "didn't catch that" in response.text
    assert "<Gather" in response.text


def test_twilio_turn_answers_speech(monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(main, "get_llm", lambda: fake_llm)
    response = TestClient(main.app).post("/twilio/turn", data={"CallSid": "CA2", "SpeechResult": "any deals"})
    assert "WINTER15" in response.text
    assert "<Gather" in response.text


def test_twilio_turn_escapes_xml(monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(main, "get_llm", lambda: lambda m, t: {"role": "assistant", "content": "Tom & Jerry <b>"})
    response = TestClient(main.app).post("/twilio/turn", data={"CallSid": "CA3", "SpeechResult": "hi"})
    assert "Tom &amp; Jerry &lt;b&gt;" in response.text


def test_twilio_rejects_unsigned_requests_when_token_set(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-test-token")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.ngrok.app")
    response = TestClient(main.app).post("/twilio/voice")
    assert response.status_code == 403
