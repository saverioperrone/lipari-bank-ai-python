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
├── config.py               # Pydantic Settings, loaded from .env
├── main.py                 # FastAPI app, middleware, exception handler, router registration
├── exceptions.py            # AppError e sottoclassi di dominio
├── api/
│   ├── chat.py              # POST /api/ai/chat (echo)
│   └── categorize.py        # POST /api/ai/categorize (dummy by keyword)
├── types/
│   ├── chat.py               # ChatRequest, ToolCallInfo, ChatResponse
│   ├── categorize.py         # CategorizeRequest, CategorizeResponse
│   ├── advice.py             # AdviceRequest, AdviceResponse, Citation (anticipato, nessun endpoint ancora)
│   └── error.py              # ErrorResponse
└── lipari_bank_ai/
    └── __init__.py         # installable package entry point
```

## API

| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/ai/chat` | Chat AI — echo (LLM reale in G4) |
| POST | `/api/ai/categorize` | Categorizzazione transazione — dummy by keyword (LLM reale in G4) |

Tutti gli errori (custom `AppError`, validazione Pydantic, eccezioni impreviste) tornano nello stesso formato JSON: `timestamp`, `status`, `error`, `message`, `path` (+ `details` per la validazione). Ogni response include l'header `X-Request-Id`.

## Decisione di design — response_model esplicito vs return type hint

Sui due endpoint di oggi uso `response_model` esplicito (`response_model=ChatResponse`, `response_model=CategorizeResponse`) invece di fidarmi solo del return type hint. Il return type hint lo legge mypy in fase di sviluppo ma non viene eseguito a runtime; `response_model` invece valida e filtra davvero l'output ad ogni richiesta, anche se il service dovesse un giorno restituire per errore un campo in più (es. un id interno). Su endpoint pubblici preferisco il controllo più rigido a runtime, anche a costo di qualche riga in più nel decoratore.

## Difetti trovati nello starter di Gino

Confrontando `starter-collega/` con il codice di riferimento del progetto:

- **`AppException` invece di `AppError`** (`src/exceptions.py`): nome della classe base diverso da quello richiesto/insegnato. Corretto rinominando classe base e sottoclassi.
- **`class Config` in `ChatResponse`** (`src/types/chat.py`): sintassi Pydantic v1 per l'esempio Swagger — in v2 viene ignorata in silenzio, quindi non produce alcun effetto. Rimossa.
- **`response_model` mancante su `/api/ai/chat`** (`src/api/chat.py`): l'endpoint non dichiarava `response_model=ChatResponse`, quindi né la validazione dell'output né lo schema in `/docs` erano garantiti. Aggiunto.
- **Handler generico che espone l'errore e risponde 200** (`src/main.py`): `general_exception_handler` faceva `JSONResponse(content={"error": str(exc)})` senza `status_code` esplicito (default 200) e con il messaggio d'errore reale esposto al client. Corretto con `status_code=500` esplicito e messaggio generico — nessuno stack trace in risposta.
