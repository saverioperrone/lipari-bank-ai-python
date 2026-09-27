from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import EMBEDDING_DIM
from src.db.session import get_db
from src.llm.embedding_client import EmbeddingClient
from src.llm.factory import get_llm_provider
from src.services.ingest_service import IngestService
from src.services.rag_service import RAGService
from src.services.retrieval_service import RetrievalService
from src.types.advice import AdviceRequest, AdviceResponse, IngestRequest, IngestResponse

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Il percorso e' costruito dal file, non dalla directory di lavoro: il server puo'
# essere avviato da qualunque cartella. Stessa convenzione di src/api/chat.py.
PROMPT = (Path(__file__).parent.parent / "prompts" / "advisor_system.md").read_text(
    encoding="utf-8"
)


@router.post("/advice", response_model=AdviceResponse)
async def advice(req: AdviceRequest, db: AsyncSession = Depends(get_db)) -> AdviceResponse:
    """Costruisce i servizi per QUESTA richiesta e delega. Nessuna logica qui dentro."""
    retrieval = RetrievalService(db, EmbeddingClient())
    return await RAGService(retrieval, EmbeddingClient(), get_llm_provider(), PROMPT).advise(req)


@router.post("/documents/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest, db: AsyncSession = Depends(get_db)) -> IngestResponse:
    """Scrive l'indice. Lento per costruzione: un documento lungo supera i timeout."""
    quanti = await IngestService(db, EmbeddingClient()).ingest(req.document_id, req.content)
    return IngestResponse(chunk_count=quanti, embedding_dim=EMBEDDING_DIM)
