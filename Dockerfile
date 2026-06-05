FROM python:3.11-slim

# Variables de entorno para ahorrar espacio y evitar errores de logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TF_CPP_MIN_LOG_LEVEL=3
ENV PORT=8000

# Instalación de dependencias del sistema (minimizada)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia e instala requirements
# Tip: Asegúrate de que en requirements.txt NO esté torch si usas TensorFlow
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia el resto del código
COPY . .

# Verificaciones ligeras (sin cargar TensorFlow en memoria)
RUN test -f modelo/modelo_resnet50.keras || (echo "ERROR: Modelo no encontrado" && exit 1) && \
    echo "✓ Archivos necesarios verificados"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["sh", "-c", "echo '[startup] Iniciando...' && uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]