FROM python:3.11-slim

# Instalar librerías del sistema necesarias para OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar dependencias e instalar
COPY requirements.txt .
# Reemplazamos opencv-python por headless (no necesita interfaz gráfica)
RUN sed -i 's/opencv-python/opencv-python-headless/g' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn

# Copiar el resto del código
COPY . .

# Crear carpetas para datos persistentes
RUN mkdir -p data config models

# Exponer el puerto (Render asigna uno dinámicamente)
EXPOSE 5000

# Comando para iniciar con Gunicorn (1 worker, 4 hilos)
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 wsgi:app
