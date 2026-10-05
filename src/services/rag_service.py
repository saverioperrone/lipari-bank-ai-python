import asyncio
import logging
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass

from src.auth.deps import UserContext
from src.exceptions import LLMProviderError
from src.llm.client import LLMProvider
from src.llm.embedding_client import EmbeddingClient
from src.llm.rewriter import QueryRewriter
from src.llm.types import LLMResponse, Message
from src.services.retrieval_service import RetrievalResult, RetrievalService
from src.types.advice import AdviceResponse, Citation

logger = logging.getLogger(__name__)

RIFIUTO = "Non ho trovato informazioni sufficienti nei documenti disponibili."

PASSAGGI = 5  # quanti passaggi finiscono nel contesto

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


def contesto(passaggi: list[RetrievalResult]) -> str:
    """I passaggi numerati come [fonte-N]: e' la numerazione che `citate` rilegge."""
    return "\n\n".join(
        f"[fonte-{i}] (documento: {p.document_id})\n{p.content}"
        for i, p in enumerate(passaggi, start=1)
    )


@dataclass
class Fasi:
    """Millisecondi per fase, per il log strutturato della richiesta."""

    auth_ms: int = 0
    rewrite_ms: int = 0
    embedding_ms: int = 0
    retrieval_ms: int = 0
    prompt_ms: int = 0
    llm_ms: int = 0
    cache_hit: bool = False
    used_fallback: bool = False

    @property
    def total_ms(self) -> int:
        return (
            self.auth_ms
            + self.rewrite_ms
            + self.embedding_ms
            + self.retrieval_ms
            + self.prompt_ms
            + self.llm_ms
        )


@contextmanager
def _cronometro(fasi: Fasi, campo: str) -> Iterator[None]:
    inizio = time.perf_counter()
    try:
        yield
    finally:
        setattr(fasi, campo, int((time.perf_counter() - inizio) * 1000))


class RAGService:
    """Riscrive la domanda, recupera per ruolo, genera con le fonti."""

    # Scelto, non copiato: qui il modello locale genera in 15-18 secondi, e i 10 della
    # pagina, pensati per un modello in cloud, taglierebbero ogni risposta vera.
    TIMEOUT_GENERAZIONE_S: float = 30

    def __init__(
        self,
        retrieval: RetrievalService,
        embedder: EmbeddingClient,
        llm: LLMProvider,
        rewriter: QueryRewriter,
        prompt: str,
    ) -> None:
        self.retrieval = retrieval
        self.embedder = embedder
        self.llm = llm
        self.rewriter = rewriter
        self.prompt = prompt

    async def advise(self, question: str, user: UserContext) -> AdviceResponse:
        """Le fasi di /advice, cronometrate una per una.

        La domanda riscritta serve solo a cercare: al modello va quella dell'utente.
        Se il recupero non porta niente sopra la soglia, ritorna la frase di rifiuto
        e nessuna citazione: non chiama il modello.
        """
        fasi = Fasi()

        with _cronometro(fasi, "rewrite_ms"):
            search_query = await self.rewriter.rewrite_cached(question)

        with _cronometro(fasi, "embedding_ms"):
            query_vec = await self.embedder.embed_one(search_query)

        with _cronometro(fasi, "retrieval_ms"):
            chunks = await self.retrieval.search_for_user(query_vec, user.role, top_k=PASSAGGI)

        if not chunks:
            return AdviceResponse(
                answer=RIFIUTO,
                citations=[],
                tokens_used=0,
                cost_eur=0.0,
                rewritten_query=search_query,
            )

        with _cronometro(fasi, "prompt_ms"):
            # La riscritta serve al retrieval. Al modello va la domanda dell'utente.
            messaggi = [
                Message(role="system", content=self.prompt),
                Message(
                    role="user",
                    content=f"CONTESTO\n{contesto(chunks)}\n\nDOMANDA\n{question}",
                ),
            ]

        with _cronometro(fasi, "llm_ms"):
            risposta, fasi.used_fallback = await self._generate_or_degrade(messaggi, chunks)

        logger.info(
            "advice_completata",
            extra={
                "username": user.username,
                "role": user.role,
                "chunk_count": len(chunks),
                "chunk_ids": [r.chunk_id for r in chunks],
                **asdict(fasi),
                "total_ms": fasi.total_ms,
            },
        )
        return AdviceResponse(
            answer=risposta.content,
            citations=citate(risposta.content, chunks),
            tokens_used=risposta.tokens_used,
            cost_eur=risposta.cost_eur,
            rewritten_query=search_query,
        )

    async def _generate_or_degrade(
        self, messaggi: list[Message], chunks: list[RetrievalResult]
    ) -> tuple[LLMResponse, bool]:
        try:
            async with asyncio.timeout(self.TIMEOUT_GENERAZIONE_S):
                return await self.llm.complete(messaggi, max_tokens=500), False
        except (LLMProviderError, TimeoutError):
            logger.warning("generator_non_disponibile_fallback_su_chunk")
            estratti = "\n\n".join(
                f"[fonte-{i}] {r.document_id}\n{r.content}"
                for i, r in enumerate(chunks[:3], start=1)
            )
            testo = (
                "⚠️ Risposta parziale: il servizio di sintesi non è momentaneamente "
                "disponibile. Di seguito i passaggi dei documenti più pertinenti "
                f"alla tua domanda.\n\n{estratti}"
            )
            return LLMResponse(content=testo, tokens_used=0, cost_eur=0.0, model="nessuno"), True
