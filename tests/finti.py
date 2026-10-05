"""I modelli finti dei test: nessun test chiama un modello vero.

Costerebbe, e risponderebbe ogni volta in un modo diverso. Gli embedding finti sono
coerenti: testi con parole in comune hanno vettori vicini, quindi il recupero dei test
si comporta come quello vero, solo senza Ollama.
"""

import hashlib
import math
import re

from src.auth.deps import UserContext
from src.db.models import EMBEDDING_DIM
from src.llm.embedding_client import EmbeddingClient
from src.llm.rewriter import QueryRewriter
from src.llm.types import LLMResponse, Message


def vettore(testo: str) -> list[float]:
    """Un vettore da EMBEDDING_DIM dimensioni, ricavato dalle parole del testo.

    Ogni parola accende la dimensione scelta dal suo hash: due testi con parole in comune
    hanno coseno alto, due testi senza parole in comune quasi zero. La prima dimensione e'
    sempre accesa, cosi' nessun vettore e' nullo: il coseno di un vettore nullo non esiste.
    """
    v = [0.0] * EMBEDDING_DIM
    v[0] = 1.0
    for parola in re.findall(r"\w+", testo.lower()):
        v[1 + int(hashlib.md5(parola.encode()).hexdigest(), 16) % (EMBEDDING_DIM - 1)] += 1.0
    norma = math.sqrt(sum(x * x for x in v))
    return [x / norma for x in v]


class EmbedderFinto(EmbeddingClient):
    """Lo stesso contratto di EmbeddingClient, con i vettori di `vettore` e senza Ollama."""

    def __init__(self) -> None:  # niente client: questo embedder non chiama nessuno
        pass

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [vettore(t) for t in texts]

    async def embed_one(self, text: str) -> list[float]:
        return vettore(text)


def embedder_finto() -> EmbedderFinto:
    return EmbedderFinto()


class ModelloEco:
    """La chat dei test: risponde ripetendo l'ultima domanda dell'utente."""

    async def complete(self, messages: list[Message], max_tokens: int = 500) -> LLMResponse:
        domanda = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return LLMResponse(content=domanda, tokens_used=1, cost_eur=0.0, model="eco")


class ModelloFisso:
    """Un modello che risponde sempre lo stesso testo, deciso dal test."""

    def __init__(self, testo: str) -> None:
        self.testo = testo

    async def complete(self, messages: list[Message], max_tokens: int = 500) -> LLMResponse:
        return LLMResponse(content=self.testo, tokens_used=1, cost_eur=0.0, model="fisso")


MARCO = UserContext(username="mbianchi", role="operator")  # chi chiede, nei test senza token
GIULIA = UserContext(username="grossi", role="compliance_lead")


def riscrittore_spento() -> QueryRewriter:
    """Il riscrittore dei test che non parlano di riscrittura: la domanda passa com'è."""
    return QueryRewriter(ModelloEco(), "", enabled=False)
