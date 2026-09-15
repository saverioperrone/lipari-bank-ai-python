import time
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import RequestResponseEndpoint

from src.api import categorize, chat
from src.config import settings
from src.exceptions import AppError


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
async def add_request_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = str(uuid.uuid4())
    start = time.time()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Process-Time"] = str(time.time() - start)
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
