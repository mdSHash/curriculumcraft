# HF Spaces variant of backend/Dockerfile.
# Differences from backend/Dockerfile:
#   - Runs as non-root user (UID 1000) — required by HF Spaces
#   - Uses --user pip install so packages land in /home/user/.local
#   - HF mounts a 50 GB ephemeral volume at /data — we point the app at it
#     so generated workbooks and FAISS indices survive request boundaries
#     (still wiped on Space restart).

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ara \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/app/.cache/huggingface \
    DB_PATH=/home/user/app/data/mathcraft.db \
    UPLOAD_DIR=/home/user/app/data/uploads \
    OUTPUT_DIR=/home/user/app/data/workbooks \
    FAISS_DIR=/home/user/app/data/faiss_indices

WORKDIR /home/user/app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user:user . .

RUN mkdir -p data/uploads data/workbooks data/faiss_indices

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
