FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV TF_ENABLE_ONEDNN_OPTS=0
ENV TF_CPP_MIN_LOG_LEVEL=2
ENV OMP_NUM_THREADS=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    python -c "import tensorflow as tf; print(f'TensorFlow {tf.__version__} loaded successfully')"

COPY . .

RUN test -f modelo/modelo_resnet50.keras || (echo "ERROR: modelo/modelo_resnet50.keras not found" && exit 1) && \
    test -f index.html || (echo "ERROR: index.html not found" && exit 1) && \
    echo "✓ All required files present"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["sh", "-c", "echo '[startup] Starting Gestion Documental on port ${PORT:-8000}' && uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
