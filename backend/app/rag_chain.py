"""Build the LCEL RAG chain: retriever -> prompt -> LLM -> parser."""
from functools import lru_cache

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_groq import ChatGroq

from .config import get_settings
from .db import get_retriever


SYSTEM_PROMPT = (
    "You are a precise assistant. Answer the user's question using ONLY "
    "the context provided below. If the answer isn't in the context, say "
    "you don't know. Be concise.\n\n"
    "Context:\n{context}"
)


@lru_cache(maxsize=1)
def _get_llm() -> ChatGroq:
    """Lazily build the ChatGroq client. Reads CHAT_API_KEY on first call,
    not at module import — so importing this module doesn't require the key."""
    s = get_settings()
    return ChatGroq(model=s.llm_model, api_key=s.chat_api_key, temperature=0)


_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{question}"),
])


def _format_docs(docs) -> str:
    return "\n\n".join(
        f"[{i}] (page {doc.metadata.get('page', '?')}) {doc.page_content}"
        for i, doc in enumerate(docs, start=1)
    )


def _make_sources(docs) -> list[dict]:
    return [
        {"page": d.metadata.get("page"), "snippet": d.page_content[:200]}
        for d in docs
    ]


def ask(collection: str, question: str, k: int = 4) -> dict:
    """Retrieve context, prompt the LLM, return {answer, sources}.

    Uses the standard LCEL RAG pattern (CampusX Video 14):
        question -> {context: retriever|format_docs, question: passthrough}
                -> prompt -> llm -> parser
    """
    llm = _get_llm()
    retriever = get_retriever(collection, k=k)
    chain = (
        {
            "context": retriever | _format_docs,
            "question": RunnablePassthrough(),
        }
        | _prompt
        | llm
        | StrOutputParser()
    )

    # We invoke the chain for the answer, then the retriever again to grab
    # the source docs we display to the user.
    answer = chain.invoke(question)
    docs = retriever.invoke(question)
    return {"answer": answer, "sources": _make_sources(docs)}
