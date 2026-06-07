"""RAG chain: history-aware retrieval + streaming answers.

Heavy resources (embedding model, vector store, LLM) are initialised lazily and
cached at module level so the web process boots fast and shares one instance
across requests.
"""
import logging
import threading

from flask import current_app
from langchain.chains import (
    create_history_aware_retriever,
    create_retrieval_chain,
)
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_pinecone import PineconeVectorStore

from src.helper import download_hugging_face_embeddings
from src.prompt import contextualize_q_prompt, system_prompt

logger = logging.getLogger(__name__)

_chain = None
_lock = threading.Lock()


def _build_chain():
    cfg = current_app.config
    embeddings = download_hugging_face_embeddings()
    docsearch = PineconeVectorStore.from_existing_index(
        index_name=cfg["PINECONE_INDEX"],
        embedding=embeddings,
    )
    retriever = docsearch.as_retriever(
        search_type="similarity", search_kwargs={"k": 3}
    )
    llm = ChatOpenAI(model=cfg["OPENAI_MODEL"], temperature=0)

    contextualize_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_prompt
    )

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    qa_chain = create_stuff_documents_chain(llm, qa_prompt)
    return create_retrieval_chain(history_aware_retriever, qa_chain)


def get_chain():
    global _chain
    if _chain is None:
        with _lock:
            if _chain is None:
                logger.info("Building RAG chain (first request)...")
                _chain = _build_chain()
    return _chain


def to_lc_history(messages):
    """Convert DB Message rows to LangChain message objects."""
    history = []
    for m in messages:
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            history.append(AIMessage(content=m.content))
    return history


def stream_answer(question: str, history):
    """Yield answer tokens, then a final dict with source documents.

    Yields tuples: ("token", str) for each chunk, ("done", {sources}) at end.
    """
    chain = get_chain()
    sources = []
    payload = {"input": question, "chat_history": history}
    for chunk in chain.stream(payload):
        if "context" in chunk:
            for doc in chunk["context"]:
                src = (doc.metadata or {}).get("source")
                if src and src not in sources:
                    sources.append(src)
        if "answer" in chunk and chunk["answer"]:
            yield ("token", chunk["answer"])
    yield ("done", {"sources": sources})
