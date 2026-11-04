FROM python:3.12-slim

# Install Tesseract OCR (French & English) and poppler-utils for pdf2image
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files, default categories schema, and tests
COPY app/ app/
COPY tests/ tests/
COPY categories.yaml ./

# Create data directory
RUN mkdir -p /app/data/documents

EXPOSE 8000

ARG TAG=dev
ENV TAG=${TAG}
ENV DATA_DIR=/app/data
ENV STORAGE_DIR=/app/data/documents
ENV DB_PATH=/app/data/lazydocs.db

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
