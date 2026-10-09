import re
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded

from src.api import admin, advice, agent, auth, categorize, chat
from src.config import settings
from src.exceptions import AppError
from src.observability.json_log import configura_log, request_id

configura_log()  # Giorno 9: le righe di log diventano JSON, con il request_id
ID_VALIDO = re.compile(r"[A-Za-z0-9-]{8,64}")  # dal Giorno 2: la forma di un id che si riusa


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    app_name: str
    version: str


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Bootcamp Python AI Powered v1 — Lipari Consulting",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.middleware("http")
async def add_request_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Se il chiamante ne manda uno, lo stesso id attraversa i due sistemi; se non lo manda,
    # o manda qualcosa che non ha la forma di un id, se ne genera uno nuovo.
    ricevuto = request.headers.get("X-Request-Id", "")
    rid = ricevuto if ID_VALIDO.fullmatch(ricevuto) else str(uuid.uuid4())
    request_id.set(rid)  # Giorno 9: da qui ogni riga di log di questa richiesta lo porta
    inizio = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    response.headers["X-Process-Time"] = f"{time.perf_counter() - inizio:.4f}"
    return response


@app.exception_handler(AppError)
async def app_exception_handler(req: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "timestamp": datetime.now(UTC).isoformat(),
            "status": exc.status_code,
            "error": exc.code,
            "message": exc.message,
            "path": req.url.path,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(req: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "timestamp": datetime.now(UTC).isoformat(),
            "status": 422,
            "error": "VALIDATION_ERROR",
            "message": "Input non valido",
            "path": req.url.path,
            "details": [f"{e['loc'][-1]}: {e['msg']}" for e in exc.errors()],
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(req: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "timestamp": datetime.now(UTC).isoformat(),
            "status": 500,
            "error": "INTERNAL_ERROR",
            "message": "Errore inatteso",
            "path": req.url.path,
        },
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="UP",
        timestamp=datetime.now(UTC).isoformat(),
        app_name=settings.app_name,
        version="1.0.0",
    )


app.include_router(chat.router)
app.include_router(categorize.router)
app.include_router(advice.router)
app.include_router(auth.router)
app.include_router(agent.router)
app.include_router(admin.router)  # Giorno 9: il rapporto sui costi

app.state.limiter = advice.limiter  # slowapi lo cerca qui


@app.exception_handler(RateLimitExceeded)
async def handle_rate_limit(req: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": "60"},
        content={
            "timestamp": datetime.now(UTC).isoformat(),
            "status": 429,
            "error": "RATE_LIMIT",
            "message": "Troppe richieste: riprova fra un minuto",
            "path": req.url.path,
        },
    )
