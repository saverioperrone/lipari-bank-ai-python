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
    similarity: float = Field(..., ge=0.0, le=1.0)


class AdviceRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class AdviceResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    tokens_used: int = Field(default=0, ge=0)
    cost_eur: float = Field(default=0.0, ge=0)


class IngestRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class IngestResponse(BaseModel):
    chunk_count: int = Field(..., ge=0)
    embedding_dim: int = Field(..., gt=0)
