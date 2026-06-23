# Stage 1 - Builder
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install --only-binary :all: -r requirements.txt || \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2 - Runtime
FROM python:3.11-slim AS runtime
RUN groupadd -r appgroup && useradd -r -g appgroup -s /bin/false appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=appuser:appgroup main.py config.py azure_secrets.py ./
COPY --chown=appuser:appgroup services/ ./services/
USER appuser
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
