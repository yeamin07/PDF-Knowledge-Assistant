"""HuggingFace Spaces entry: a single Streamlit app that runs the RAG pipeline in-process.

Replaces the old FastAPI + Streamlit split. Uses the same backend modules
(ingestion.py, rag_chain.py, db.py) directly — no HTTP, no BACKEND_URL.

Run with: `streamlit run app.py --server.port 7860 --server.address 0.0.0.0`
HF Spaces sets --server.port to 7860 by default for Streamlit SDK.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

import streamlit as st

# Import backend modules — these run in the same process.
from backend.app.ingestion import ingest_pdf
from backend.app.rag_chain import ask as ask_rag

COLLECTION = os.getenv("COLLECTION", "pdf_docs")


def _ingest_bytes(pdf_bytes: bytes, filename: str, collection: str) -> dict:
    """Write bytes to a temp file and run the existing ingest_pdf."""
    tmp_dir = tempfile.mkdtemp()
    save_path = os.path.join(tmp_dir, filename)
    with open(save_path, "wb") as out:
        out.write(pdf_bytes)
    try:
        return ingest_pdf(save_path, collection)
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass


st.set_page_config(page_title="RAG PDF QA", page_icon="📄", layout="centered")
st.title("📄 RAG PDF QA")
st.caption("Upload a PDF, then ask questions grounded in its content.")

st.header("1. Upload a PDF")
uploaded = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded is not None and st.button("Ingest this PDF", type="primary"):
    with st.spinner("Loading, splitting, embedding, storing..."):
        try:
            result = _ingest_bytes(uploaded.getvalue(), uploaded.name, COLLECTION)
            st.session_state["last_ingest"] = result
            st.success(
                f"Ingested **{uploaded.name}** — "
                f"{result['pages']} pages, {result['chunks']} chunks "
                f"into collection `{result['collection']}`."
            )
        except ValueError as exc:
            st.error(f"Ingest failed: {exc}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Ingest failed: {exc!r}")

st.header("2. Ask a question")
question = st.text_input("Your question", placeholder="What is this document about?")
k = st.slider("Top-k", min_value=1, max_value=20, value=4)

if st.button("Ask", type="primary", disabled=not question) and question:
    with st.spinner("Retrieving context and generating answer..."):
        try:
            payload: dict[str, Any] = {"question": question, "collection": COLLECTION, "k": int(k)}
            result = ask_rag(
                collection=payload["collection"],
                question=payload["question"],
                k=payload["k"],
            )
        except ValueError as exc:
            st.error(f"No PDF ingested yet — {exc}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Ask failed: {exc!r}")
        else:
            st.subheader("Answer")
            st.write(result["answer"])

            sources = result.get("sources") or []
            if sources:
                with st.expander(f"Sources ({len(sources)})"):
                    for i, s in enumerate(sources, start=1):
                        page = s.get("page")
                        page_str = f"page {page}" if page is not None else "page ?"
                        st.markdown(f"**[{i}] {page_str}**")
                        st.write(s.get("snippet", ""))
