from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Un passaggio citato dalla risposta, con da dove viene e quanto era vicino.

    Qui ci finiscono solo i passaggi il cui marcatore [fonte-N] compare davvero nel
    testo della risposta, non tutti quelli che il recupero ha portato: allegarli tutti
    farebbe passare per prova anche il passaggio che il modello non ha guardato.

    Resta un limite da sapere: che il marcatore ci sia non garantisce che quel passaggio
    sostenga la frase a cui e' attaccato. Vedi docs/ai-review/G5.md, rilievo 3.
    """

    document_id: str
    chunk_id: str
    excerpt: str
    similarity: float


class AdviceRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)


class AdviceResponse(BaseModel):
    answer: str
    citations: list[Citation]
    tokens_used: int
    cost_eur: float


class IngestRequest(BaseModel):
    document_id: str = Field(..., max_length=100)
    content: str = Field(..., min_length=10)
    # `dict[str, str]` e non `dict`: mypy in strict rifiuta i generici nudi, ed e' lo
    # stesso tipo della colonna `chunk_metadata` in cui questi dati finiscono.
    metadata: dict[str, str] | None = None


class IngestResponse(BaseModel):
    chunk_count: int
    embedding_dim: int
