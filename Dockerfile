# Dockerfile — due fasi: si costruisce con uv, si esegue senza

# ── Fase 1: costruzione ──────────────────────────────────────────
FROM python:3.12-slim AS builder

# uv con la sua versione scritta: `latest` cambierebbe sotto i piedi a ogni build
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

# Solo i manifest: questo layer si rifà solo se cambiano le dipendenze
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Il codice dopo: cambia a ogni commit, e invalida solo da qui in giù. Il progetto non è un
# pacchetto, quindi non si installa: si copia, e gira dalla cartella di lavoro
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY scripts ./scripts
COPY evals ./evals
COPY liparibank_mcp ./liparibank_mcp
COPY data ./data

# ── Fase 2: esecuzione ───────────────────────────────────────────
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 lipari
WORKDIR /app

COPY --from=builder --chown=lipari:lipari /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

USER lipari
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status==200 else 1)"

CMD ["gunicorn", "src.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "2", "--bind", "0.0.0.0:8000", \
     "--max-requests", "1000", "--max-requests-jitter", "100", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]
