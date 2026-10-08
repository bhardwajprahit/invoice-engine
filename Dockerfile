FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TESSERACT_PATH=/usr/bin/tesseract

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT}"]
