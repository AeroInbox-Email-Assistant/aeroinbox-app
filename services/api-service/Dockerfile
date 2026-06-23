# Stage 1 - Builder
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install --only-binary :all: --require-hashes -r requirements.txt

# Stage 2 - Runtime
FROM python:3.11-slim AS runtime
RUN groupadd -r appgroup && useradd -r -g appgroup -s /bin/false appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=root:root main.py auth_deps.py database.py redis_client.py azure_secrets.py ./
COPY --chown=root:root config/ ./config/
COPY --chown=root:root routes/ ./routes/
USER appuser
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
