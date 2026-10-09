FROM python:3.11-slim

ARG OPC_EXTRAS="documents,openai"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY opc_agent ./opc_agent
COPY examples ./examples

RUN pip install --upgrade pip \
    && pip install ".[${OPC_EXTRAS}]" \
    && groupadd --system --gid 10001 opcuser \
    && useradd --system --uid 10001 --gid opcuser \
        --home-dir /app --shell /usr/sbin/nologin opcuser \
    && mkdir -p /data/outputs \
    && chown -R opcuser:opcuser /app /data

USER opcuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3)"]

CMD ["python", "-m", "opc_agent.web", \
    "--host", "0.0.0.0", \
    "--port", "8080", \
    "--output-dir", "/data/outputs", \
    "--examples-dir", "/app/examples"]
