"""Process-wide dependencies, built once at startup and torn down at shutdown."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.auth.email import OutboxEmailSender
from app.core.config import Settings
from app.core.kv import KV, build_kv
from app.db.session import build_engine, build_sessionmaker
from app.policies.service import COLLECTION as POLICY_COLLECTION
from app.policies.service import PolicyLibrary
from app.rag.bm25 import BM25Encoder
from app.rag.embeddings import Embedder, build_embedder
from app.rag.generate import ExtractiveGenerator, Generator, LLMGenerator, ResilientGenerator
from app.rag.llm import AnthropicChat, ChatModel, FallbackChat, GeminiChat, OllamaChat, OpenAIChat
from app.rag.pipeline import AnswerPipeline
from app.rag.rerank import Reranker, build_reranker
from app.rag.retriever import HybridRetriever
from app.rag.store import VectorStore
from app.triage.compose import MedicineCheck

PROVIDER_ORDER: dict[str, tuple[str, ...]] = {
    "auto": ("openai", "gemini", "anthropic"),
    "openai": ("openai", "gemini", "anthropic"),
    "gemini": ("gemini", "openai", "anthropic"),
    "anthropic": ("anthropic", "openai", "gemini"),
    "ollama": ("ollama",),
}


def llm_chain(s: Settings) -> list[ChatModel]:
    """Models to try, in order: the chosen provider first, then any other provider with a key."""
    t = s.llm_timeout_seconds
    makers: dict[str, ChatModel | None] = {
        "openai": OpenAIChat(s.openai_api_key, s.openai_model, t) if s.openai_api_key else None,
        "gemini": GeminiChat(s.gemini_api_key, s.gemini_model, t) if s.gemini_api_key else None,
        "anthropic": AnthropicChat(s.anthropic_api_key, s.anthropic_model, t)
        if s.anthropic_api_key
        else None,
        "ollama": OllamaChat(s.ollama_url, s.ollama_model, timeout=t * 4)
        if s.llm_provider == "ollama"
        else None,
    }
    return [m for name in PROVIDER_ORDER.get(s.llm_provider, ()) if (m := makers[name]) is not None]


def build_generator(s: Settings) -> Generator:
    if s.llm_provider == "extractive":
        return ExtractiveGenerator()
    chain = llm_chain(s)
    if not chain:  # "auto" with no key yet: free extractive mode
        return ExtractiveGenerator()
    chat: ChatModel = chain[0] if len(chain) == 1 else FallbackChat(*chain)
    return ResilientGenerator(LLMGenerator(chat), ExtractiveGenerator())


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = build_engine(settings.database_url)
        self.sessionmaker: async_sessionmaker[AsyncSession] = build_sessionmaker(self.engine)
        self.kv: KV = build_kv(settings.redis_url)
        self.mailer = OutboxEmailSender(echo_body=settings.env == "dev")
        self.embedder: Embedder = build_embedder(
            settings.embeddings_provider,
            model=settings.embeddings_model,
            dim=settings.embeddings_dim,
            openai_key=settings.openai_api_key,
        )
        self.store = VectorStore.from_settings(
            url=settings.qdrant_url,
            path=settings.qdrant_path,
            api_key=settings.qdrant_api_key,
            collection=settings.qdrant_collection,
            dim=self.embedder.dim,
        )
        self.bm25 = BM25Encoder()
        self.reranker: Reranker = build_reranker(
            settings.rerank_provider,
            model=settings.rerank_model,
            cohere_key=settings.cohere_api_key,
        )
        self.retriever = HybridRetriever(
            self.store,
            self.embedder,
            self.reranker,
            self.bm25,
            retrieve_k=settings.retrieve_k,
            context_k=settings.context_k,
        )
        self.generator = build_generator(settings)
        self.pipeline = AnswerPipeline(
            self.retriever,
            self.generator,
            abstain_threshold=settings.abstain_threshold
            if settings.abstain_threshold is not None
            else self.reranker.default_threshold,
            groundedness_threshold=settings.groundedness_threshold,
            kv=self.kv,
            corpus_tag=settings.qdrant_collection,
            medicine=MedicineCheck(self.store, self.retriever),
        )
        # Insurance policy library (separate demo): own collection on the same Qdrant client.
        self.policies = PolicyLibrary(
            Path(settings.policies_dir),
            VectorStore(self.store.client, POLICY_COLLECTION, self.embedder.dim),
            self.embedder,
            self.reranker,
            self.bm25,
            abstain_threshold=self.pipeline.abstain_threshold,
        )

    async def startup(self) -> None:
        if self.settings.db_auto_create:
            # dev/test convenience; staging/prod run `alembic upgrade head` before deploy
            from app.db.models import Base

            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        await self.store.ensure()

    async def shutdown(self) -> None:
        for obj in (self.generator, self.reranker, self.embedder):
            inner = getattr(obj, "chat", obj)
            for target in (
                inner,
                getattr(inner, "primary", None),
                getattr(inner, "secondary", None),
            ):
                close = getattr(target, "aclose", None)
                if close is not None:
                    await close()
        await self.store.close()
        await self.kv.close()
        await self.engine.dispose()
