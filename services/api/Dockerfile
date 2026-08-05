FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# torch is installed in the same resolution pass as everything else, with
# the CPU-only wheel index as primary. Installing it as a separate prior
# step (as before) doesn't stick: requirements.txt also pins an exact
# torch version, so the later `pip install -r requirements.txt` call
# re-resolves torch against the default index (no --index-url in that
# invocation) and silently replaces the CPU build with the full CUDA
# build — pulling in ~4.5GB of nvidia-*/triton packages this CPU-only
# service never uses. One atomic install avoids that entirely.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir \
         --index-url https://download.pytorch.org/whl/cpu \
         --extra-index-url https://pypi.org/simple \
         -r requirements.txt

ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
RUN /opt/venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache \
    PATH=/opt/venv/bin:$PATH \
    PORT=8080

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf-cache /app/.cache
COPY app/ ./app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
