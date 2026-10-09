from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.deps import UserContext, get_current_user, require_role
from src.config import settings
from src.db.models import EMBEDDING_DIM
from src.db.repos import ChatRepository
from src.db.session import get_db
from src.llm.client import LLMProvider
from src.llm.embedding_client import EmbeddingClient
from src.llm.factory import build_llm_provider, get_embedder, get_llm_provider
from src.llm.prompt import load_prompt
from src.llm.rewriter import QueryRewriter
from src.observability.cost_tracker import CostTracker
from src.observability.ledger import CostLedger
from src.services.ingest_service import IngestService
from src.services.rag_service import RAGService
from src.services.retrieval_service import RetrievalService
from src.types.advice import AdviceRequest, AdviceResponse, IngestRequest, IngestResponse

router = APIRouter(prefix="/api/ai", tags=["ai"])

PROMPT = load_prompt("advisor_system_v2")

# La chiave e' l'utente del token, non l'IP: in filiale trenta operatori escono dallo
# stesso NAT. `request.state.username` lo scrive get_current_user.
limiter = Limiter(key_func=lambda request: request.state.username)

riscrittore = QueryRewriter(build_llm_provider(temperature=0), load_prompt("rewrite_system_v2"))


def get_rewriter() -> QueryRewriter:
    return riscrittore  # istanza unica: la cache delle riscritture vive con il processo


@dataclass
class Deps:
    rag: RAGService


async def get_deps(
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[EmbeddingClient, Depends(get_embedder)],
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
    rewriter: Annotated[QueryRewriter, Depends(get_rewriter)],
) -> Deps:
    """I servizi di /advice, da dependency: un test li sostituisce senza toccare l'endpoint."""
    return Deps(rag=RAGService(RetrievalService(db), embedder, llm, rewriter, PROMPT))


@router.post("/advice", response_model=AdviceResponse)
@limiter.limit("15/minute")
async def advice(
    request: Request,  # slowapi la pretende, e serve alla key_func
    req: AdviceRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
    deps: Annotated[Deps, Depends(get_deps)],
    session: Annotated[AsyncSession, Depends(get_db)],  # la stessa sessione dei servizi
) -> AdviceResponse:
    """I servizi arrivano da get_deps, il limite e' per utente."""
    # il tetto della chat vale anche qui: ogni chiamata al modello spende, non solo la chat
    await CostTracker(ChatRepository(session), settings.daily_budget_eur).verifica()
    risposta = await deps.rag.advise(req.question, user)
    # Giorno 9: la generazione nel registro. La riscrittura qui non c'è: vedi il Code Blueprint
    CostLedger(session).aggiungi(
        endpoint="advice",
        username=user.username,
        model=settings.default_model,
        tokens=risposta.tokens_used,
        cost_eur=Decimal(str(risposta.cost_eur)),
    )
    await session.commit()
    return risposta


async def get_ingest_service(
    db: AsyncSession = Depends(get_db),
    embedder: EmbeddingClient = Depends(get_embedder),
) -> IngestService:
    return IngestService(db, embedder)


@router.post("/documents/ingest", response_model=IngestResponse)
async def ingest(
    req: IngestRequest,
    user: Annotated[UserContext, Depends(require_role("compliance_lead", "admin"))],
    service: Annotated[IngestService, Depends(get_ingest_service)],
) -> IngestResponse:
    """Scrive l'indice: da oggi, solo la compliance e gli admin."""
    quanti = await service.ingest(req.document_id, req.content, req.metadata, req.visibility)
    return IngestResponse(chunk_count=quanti, embedding_dim=EMBEDDING_DIM)
