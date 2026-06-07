"""Chat pages + streaming API."""
import json
import logging

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from flask_login import current_user, login_required

from app.chat.rag import stream_answer, to_lc_history
from app.extensions import db, limiter
from app.models import Conversation, Message

logger = logging.getLogger(__name__)
chat_bp = Blueprint("chat", __name__)


def _get_owned_conversation(conversation_id):
    convo = db.session.get(Conversation, conversation_id)
    if convo is None or convo.user_id != current_user.id:
        abort(404)
    return convo


@chat_bp.route("/chat")
@login_required
def index():
    convos = (
        Conversation.query.filter_by(user_id=current_user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return render_template("chat.html", conversations=convos, user=current_user)


@chat_bp.route("/api/conversations", methods=["POST"])
@login_required
def create_conversation():
    convo = Conversation(user_id=current_user.id, title="New chat")
    db.session.add(convo)
    db.session.commit()
    return jsonify(id=convo.id, title=convo.title)


@chat_bp.route("/api/conversations/<int:conversation_id>/messages")
@login_required
def get_messages(conversation_id):
    convo = _get_owned_conversation(conversation_id)
    return jsonify(
        messages=[
            {"role": m.role, "content": m.content} for m in convo.messages
        ]
    )


@chat_bp.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
@login_required
def delete_conversation(conversation_id):
    convo = _get_owned_conversation(conversation_id)
    db.session.delete(convo)
    db.session.commit()
    return jsonify(ok=True)


@chat_bp.route("/api/chat", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def chat_stream():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    conversation_id = data.get("conversation_id")

    max_len = current_app.config["MAX_MESSAGE_LEN"]
    if not msg:
        return jsonify(error="empty message"), 400
    if len(msg) > max_len:
        return jsonify(error=f"message too long (max {max_len} chars)"), 400

    # Resolve or create conversation (ownership enforced)
    if conversation_id:
        convo = _get_owned_conversation(conversation_id)
    else:
        convo = Conversation(user_id=current_user.id, title=msg[:60])
        db.session.add(convo)
        db.session.commit()

    turns = current_app.config["CHAT_HISTORY_TURNS"]
    prior = convo.messages[-(turns * 2):]
    history = to_lc_history(prior)

    # Persist the user message before streaming
    db.session.add(Message(conversation_id=convo.id, role="user", content=msg))
    if convo.title == "New chat":
        convo.title = msg[:60]
    db.session.commit()
    convo_id = convo.id

    app = current_app._get_current_object()

    @stream_with_context
    def generate():
        yield _sse({"type": "meta", "conversation_id": convo_id})
        full = []
        try:
            for kind, value in stream_answer(msg, history):
                if kind == "token":
                    full.append(value)
                    yield _sse({"type": "token", "content": value})
                elif kind == "done":
                    yield _sse({"type": "done", "sources": value["sources"]})
        except Exception:
            logger.exception("Streaming failed for conversation %s", convo_id)
            yield _sse({"type": "error", "message": "Generation failed."})
            return
        finally:
            answer = "".join(full).strip()
            if answer:
                with app.app_context():
                    db.session.add(
                        Message(
                            conversation_id=convo_id,
                            role="assistant",
                            content=answer,
                        )
                    )
                    db.session.commit()

    return Response(generate(), mimetype="text/event-stream")


def _sse(obj):
    return f"data: {json.dumps(obj)}\n\n"
