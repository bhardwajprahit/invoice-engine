FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TESSERACT_PATH=/usr/bin/tesseract
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '8000') + '/health', timeout=3)" || exit 1

CMD ["sh", "-c", "python -u worker.py & exec uvicorn api:app --host 0.0.0.0 --port ${PORT}"]
