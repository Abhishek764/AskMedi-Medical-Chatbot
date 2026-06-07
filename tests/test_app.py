"""Smoke + behavior tests for the AskMedi web app."""
import app.chat.routes as chat_routes


def test_public_pages(client):
    assert client.get("/").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200
    assert client.get("/disclaimer").status_code == 200


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_chat_requires_auth(client):
    resp = client.get("/chat")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_register_logs_in_and_grants_chat(client):
    resp = client.post(
        "/register",
        data={
            "email": "new@test.com",
            "password": "password123",
            "confirm": "password123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert client.get("/chat").status_code == 200


def test_duplicate_email_rejected(client):
    payload = {
        "email": "dup@test.com",
        "password": "password123",
        "confirm": "password123",
    }
    client.post("/register", data=payload)
    client.get("/logout")
    resp = client.post("/register", data=payload, follow_redirects=True)
    assert b"already registered" in resp.data


def test_login_bad_password(auth_client):
    auth_client.get("/logout")
    resp = auth_client.post(
        "/login",
        data={"email": "user@test.com", "password": "wrong"},
        follow_redirects=True,
    )
    assert b"Invalid email or password" in resp.data


def test_empty_message_rejected(auth_client):
    resp = auth_client.post("/api/chat", json={"message": "   "})
    assert resp.status_code == 400


def test_message_too_long_rejected(auth_client):
    resp = auth_client.post("/api/chat", json={"message": "x" * 5000})
    assert resp.status_code == 400


def test_chat_stream_persists_messages(auth_client, monkeypatch):
    def fake_stream(question, history):
        for tok in ("Hi", " there", "."):
            yield ("token", tok)
        yield ("done", {"sources": ["Medical_book.pdf"]})

    monkeypatch.setattr(chat_routes, "stream_answer", fake_stream)

    resp = auth_client.post("/api/chat", json={"message": "what is fever?"})
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    body = resp.get_data(as_text=True)
    assert '"type": "meta"' in body
    assert '"type": "token"' in body
    assert "Medical_book.pdf" in body

    from app.models import Conversation, Message

    with auth_client.application.app_context():
        assert Conversation.query.count() == 1
        roles = [m.role for m in Message.query.order_by(Message.id).all()]
        assert roles == ["user", "assistant"]
        answer = Message.query.filter_by(role="assistant").first().content
        assert answer == "Hi there."


def test_conversation_ownership_enforced(auth_client):
    # Another user's conversation must not be accessible.
    from app.extensions import db
    from app.models import Conversation, User

    with auth_client.application.app_context():
        other = User(email="other@test.com")
        other.set_password("password123")
        db.session.add(other)
        db.session.commit()
        convo = Conversation(user_id=other.id, title="secret")
        db.session.add(convo)
        db.session.commit()
        convo_id = convo.id

    resp = auth_client.get(f"/api/conversations/{convo_id}/messages")
    assert resp.status_code == 404
