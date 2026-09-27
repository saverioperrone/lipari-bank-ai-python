from pydantic import BaseModel
from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncSession

from src.llm.embedding_client import EmbeddingClient

SOGLIA_PREDEFINITA = 0.35     # misurata sui documenti di LipariBank, non universale


class RetrievalResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    similarity: float


class RetrievalService:
    """La ricerca vettoriale sui passaggi dei documenti."""

    SQL = sql(
        """
        SELECT id, document_id, content,
               1 - (embedding <=> CAST(:q AS vector)) AS similarity
        FROM document_chunks
        WHERE 1 - (embedding <=> CAST(:q AS vector)) >= :soglia
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :k
        """
    )

    def __init__(self, session: AsyncSession, embedder: EmbeddingClient) -> None:
        self.session = session
        self.embedder = embedder

    async def search(
        self, query_vec: list[float], top_k: int = 5, soglia: float = SOGLIA_PREDEFINITA
    ) -> list[RetrievalResult]:
        """I passaggi più vicini alla domanda, dal più vicino.

        Prende il **vettore**, non la domanda: vettorizzare è compito di chi chiama, e
        così la stessa ricerca serve l'advisor, lo script di ingestione e l'harness di
        valutazione senza pagare un embedding che qualcuno ha già fatto.

        Sotto la soglia non torna niente: una lista vuota è una risposta, e il chiamante
        deve poterla distinguere da cinque passaggi irrilevanti.
        """
        righe = await self.session.execute(
            self.SQL, {"q": str(query_vec), "k": top_k, "soglia": soglia}
        )
        return [
            RetrievalResult(
                chunk_id=str(r.id),
                document_id=r.document_id,
                content=r.content,
                similarity=float(r.similarity),
            )
            for r in righe
        ]
