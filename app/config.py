"""Environment-driven configuration."""
import os

from dotenv import load_dotenv

load_dotenv()


def _normalize_db_url(url: str) -> str:
    # Render/Heroku hand out postgres://, SQLAlchemy 2.x needs postgresql://
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.environ.get("DATABASE_URL", "sqlite:///askmedi.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    PINECONE_INDEX = os.environ.get("PINECONE_INDEX", "medical-chatbot")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

    # Number of prior turns fed back into the RAG chain
    CHAT_HISTORY_TURNS = int(os.environ.get("CHAT_HISTORY_TURNS", "6"))
    MAX_MESSAGE_LEN = int(os.environ.get("MAX_MESSAGE_LEN", "2000"))

    RATELIMIT_DEFAULT = "200 per hour"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")


class DevConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProdConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


def get_config():
    env = os.environ.get("FLASK_ENV", "production").lower()
    return DevConfig if env in ("development", "dev") else ProdConfig
