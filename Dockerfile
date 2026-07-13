# hiremind_ai — FastAPI match/parse service + Celery worker (same image, two commands).
FROM python:3.11-slim

# System deps: poppler-utils (pdf2image), tesseract-ocr (pytesseract OCR),
# libgomp1 (xgboost/scikit-learn OpenMP runtime).
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils tesseract-ocr libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Cache HF models under a stable path we can pre-warm at build time.
ENV HF_HOME=/opt/hf-cache \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python deps first (cached layer) — copy only the project metadata.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# Pre-download the embedding model so the container starts without a network fetch.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"

# API port (uvicorn). The Celery worker overrides the command in compose.
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
