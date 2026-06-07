"""Test fixtures. Heavy RAG deps are stubbed so the suite runs without
torch/langchain/network and without API keys."""
import sys
import types

import pytest


def _install_rag_stubs():
    mods = [
        "langchain",
        "langchain.chains",
        "langchain.chains.combine_documents",
        "langchain_core",
        "langchain_core.messages",
        "langchain_core.prompts",
        "langchain_openai",
        "langchain_pinecone",
        "src.helper",
    ]
    for name in mods:
        sys.modules.setdefault(name, types.ModuleType(name))

    def _stub(*a, **k):
        return None

    for n in ("create_history_aware_retriever", "create_retrieval_chain"):
        setattr(sys.modules["langchain.chains"], n, _stub)
    setattr(
        sys.modules["langchain.chains.combine_documents"],
        "create_stuff_documents_chain",
        _stub,
    )
    for n in ("AIMessage", "HumanMessage"):
        setattr(
            sys.modules["langchain_core.messages"],
            n,
            type(n, (object,), {"__init__": lambda s, content=None: None}),
        )
    for n in ("ChatPromptTemplate", "MessagesPlaceholder"):
        setattr(sys.modules["langchain_core.prompts"], n, _stub)
    setattr(sys.modules["langchain_openai"], "ChatOpenAI", _stub)
    setattr(sys.modules["langchain_pinecone"], "PineconeVectorStore", _stub)
    setattr(sys.modules["src.helper"], "download_hugging_face_embeddings", _stub)


_install_rag_stubs()


@pytest.fixture
def app(tmp_path):
    # Build an explicit config object inside the fixture so the DB URI is set
    # before db.init_app runs. (BaseConfig reads env at import time, which is
    # too early for per-test overrides.)
    from app.config import BaseConfig

    test_config = type(
        "TestConfig",
        (BaseConfig,),
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DEBUG": True,
            "SECRET_KEY": "test",
            "SESSION_COOKIE_SECURE": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            "RATELIMIT_ENABLED": False,
        },
    )

    from app import create_app
    from app.extensions import db

    application = create_app(test_config)
    with application.app_context():
        db.create_all()
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    client.post(
        "/register",
        data={
            "email": "user@test.com",
            "password": "password123",
            "confirm": "password123",
        },
    )
    return client
