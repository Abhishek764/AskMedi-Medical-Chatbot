"""Settings loaded from environment variables (prefix-free, `.env` supported).

Every paid service sits behind a provider switch with a free local default, so the
whole backend runs with no API keys:

- LLM_PROVIDER:        extractive (default, no model) | ollama | openai | anthropic
- EMBEDDINGS_PROVIDER: hash (default, tests) | fastembed (free local) | openai
- RERANK_PROVIDER:     none (default) | fastembed (free local) | cohere
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Env = Literal["dev", "test", "staging", "prod"]

_DEV_SECRET = "dev-insecure-secret-change-me-0123456789abcdef"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Env = "dev"
    app_name: str = "AskMedi"
    api_prefix: str = "/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    # Only true when every request reaches us through Cloudflare (otherwise spoofable).
    trust_cloudflare_ip_header: bool = False

    # Storage
    database_url: str = "sqlite+aiosqlite:///./askmedi.db"
    redis_url: str | None = None  # None -> in-process KV (dev/test only)
    db_auto_create: bool = True  # create tables at startup (dev/test); False in prod

    # Auth
    jwt_secret: str = _DEV_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    min_password_length: int = 10

    # Rate limits and quotas
    rate_limit_per_minute: int = 20
    auth_rate_limit_per_minute: int = 10
    daily_question_quota: int = 50
    max_question_chars: int = 1000
    max_turns_per_conversation: int = 40

    # Retrieval
    qdrant_url: str | None = None  # None -> embedded local mode
    qdrant_path: str = "./qdrant_data"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "corpus-v1"
    raw_data_dir: str = "../data/raw"  # repo-root data/raw, relative to backend/
    policies_dir: str = "../data/policies"  # parsed insurance policies (demo library)
    embeddings_provider: Literal["hash", "fastembed", "openai"] = "hash"
    embeddings_model: str = "BAAI/bge-small-en-v1.5"
    embeddings_dim: int = 384
    rerank_provider: Literal["none", "fastembed", "cohere"] = "none"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    retrieve_k: int = 30
    context_k: int = 5
    abstain_threshold: float | None = None  # None -> the reranker's own default

    # Generation
    llm_provider: Literal["extractive", "ollama", "openai", "anthropic"] = "extractive"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    ollama_url: str = "http://localhost:11434"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    cohere_api_key: str | None = None
    groundedness_threshold: float = 0.5

    # Crisis resources (verify numbers with a clinician before launch)
    crisis_country: str = "IN"

    # Observability (optional)
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.05

    @model_validator(mode="after")
    def _check_prod_secrets(self) -> Settings:
        if self.env in ("staging", "prod"):
            if self.jwt_secret == _DEV_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a strong value outside dev/test")
            if self.database_url.startswith("sqlite"):
                raise ValueError("DATABASE_URL must be Postgres outside dev/test")
            if self.redis_url is None:
                raise ValueError("REDIS_URL is required outside dev/test")
            if self.db_auto_create:
                raise ValueError("DB_AUTO_CREATE must be false outside dev/test (use Alembic)")
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY required when LLM_PROVIDER=openai")
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY required when LLM_PROVIDER=anthropic")
        if self.rerank_provider == "cohere" and not self.cohere_api_key:
            raise ValueError("COHERE_API_KEY required when RERANK_PROVIDER=cohere")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
