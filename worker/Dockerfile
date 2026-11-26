# Сервер монтажа «Без сказок»: FFmpeg + Chromium (Playwright) + Python
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fonts-noto-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV MEDIA_DIR=/data/media STATE_DIR=/data/state PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
