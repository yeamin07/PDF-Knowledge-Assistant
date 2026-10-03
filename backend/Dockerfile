# syntax=docker/dockerfile:1.7
# ---------- Backend (FastAPI) ----------
# Image: python:3.12-slim keeps the base ~150 MB vs. ~1 GB for full python.
# We install build-essential because sentence-transformers / numpy ship
# small C extensions that need a compiler on slim images.
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface \
    PORT=8000

WORKDIR /app

# OS-level deps: build-essential for compiling C extensions, curl for HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy ONLY requirements first to leverage Docker layer cache.
COPY requirements.txt .
# Use PyTorch's CPU-only index so we don't pull ~2 GB of CUDA libraries
# (nvidia-cudnn, nvidia-cusolver, etc.). The requirements.txt also has the
# --extra-index-url line, but setting PIP_EXTRA_INDEX_URL here makes it explicit
# and lets pip resolve before hitting the regular index.
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip cache purge || true

# Copy source.
COPY app ./app

# Pre-download the embedding model (~80 MB) so the image is self-contained
# and cold starts on EC2 don't hit HuggingFace at runtime. This bloats the
# image but eliminates network-dependency on first request.
RUN python -c "from app.embeddings import get_embeddings; get_embeddings()" \
    && du -sh /app/.cache/huggingface || true

# Persistent storage for the FAISS index (mounted as a volume in compose).
RUN mkdir -p /app/.faiss_index
ENV FAISS_INDEX_DIR=/app/.faiss_index

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8000/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]