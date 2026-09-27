import re

from src.llm.client import LLMProvider
from src.llm.embedding_client import EmbeddingClient
from src.llm.types import Message
from src.services.retrieval_service import RetrievalResult, RetrievalService
from src.types.advice import AdviceRequest, AdviceResponse, Citation

RIFIUTO = "Non ho trovato informazioni sufficienti nei documenti disponibili."

PASSAGGI = 5   # quanti passaggi finiscono nel contesto

MARCATORE = re.compile(r"\[fonte-(\d+)\]")


def citate(risposta: str, passaggi: list[RetrievalResult]) -> list[Citation]:
    """Le fonti che la risposta ha davvero citato, nell'ordine in cui compaiono.

    Non i passaggi recuperati: quelli sono le fonti **consultate**, e allegarli tutti
    fa passare per prova anche il passaggio che il modello non ha guardato. Un rifiuto
    non scrive nessun marcatore, e quindi esce senza citazioni — che e' il punto.
    """
    ordine: list[int] = []
    for trovato in MARCATORE.findall(risposta):
        n = int(trovato)
        if 1 <= n <= len(passaggi) and n not in ordine:
            ordine.append(n)
    return [
        Citation(
            document_id=passaggi[n - 1].document_id,
            chunk_id=passaggi[n - 1].chunk_id,
            excerpt=passaggi[n - 1].content[:200],
            similarity=passaggi[n - 1].similarity,
        )
        for n in ordine
    ]


class RAGService:
    """Recupera i passaggi, li passa al modello come vincolo, cita le fonti."""

    def __init__(self, retrieval: RetrievalService, embedder: EmbeddingClient,
                 llm: LLMProvider, prompt: str) -> None:
        self.retrieval = retrieval
        self.embedder = embedder
        self.llm = llm
        self.prompt = prompt

    async def advise(self, req: AdviceRequest) -> AdviceResponse:
        """Recupera, genera, e ritorna la risposta con le sue fonti.

        Se il recupero non porta niente sopra la soglia, ritorna la frase di rifiuto
        e nessuna citazione: non chiama il modello.
        """
        vettore = await self.embedder.embed_one(req.question)
        passaggi = await self.retrieval.search(vettore, top_k=PASSAGGI)
        if not passaggi:
            return AdviceResponse(answer=RIFIUTO, citations=[], tokens_used=0, cost_eur=0.0)

        contesto = "\n\n".join(
            f"[fonte-{i}] (documento: {p.document_id})\n{p.content}"
            for i, p in enumerate(passaggi, start=1)
        )
        risposta = await self.llm.complete(
            [
                Message(role="system", content=self.prompt),
                Message(role="user", content=f"CONTESTO\n{contesto}\n\nDOMANDA\n{req.question}"),
            ]
        )
        return AdviceResponse(
            answer=risposta.content,
            citations=citate(risposta.content, passaggi),
            tokens_used=risposta.tokens_used,
            cost_eur=risposta.cost_eur,
        )
