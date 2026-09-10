# LipariBank AI

Bootcamp Python AI v2 — Lipari Consulting.

FastAPI backend with Pydantic Settings config, managed with uv.

## Requirements

- Python 3.12+
- uv (package manager)

## Setup

```bash
uv sync
cp .env.example .env   # then fill in real values (DB, API keys, JWT secret)
```

`uv sync` creates the virtual environment and installs all dependencies (including dev tools) from `uv.lock`.

## Run

```bash
uv run uvicorn src.main:app --reload
```

- App: http://127.0.0.1:8000
- Health check: http://127.0.0.1:8000/health
- Swagger UI: http://127.0.0.1:8000/docs

## Development

```bash
uv run ruff check src      # lint
uv run ruff format src     # format
uv run mypy src            # type check (strict)
uv run pytest              # tests
```

## Project structure

```
src/
├── config.py              # Pydantic Settings, loaded from .env
├── main.py                # FastAPI app + /health endpoint
└── lipari_bank_ai/
    └── __init__.py        # installable package entry point
```

## Environment variables

See `.env.example` for the full list of required variables (database URL, OpenAI/Anthropic API keys, JWT secret, model config). `.env` is git-ignored and must be created locally.
