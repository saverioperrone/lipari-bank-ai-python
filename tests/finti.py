"""I modelli finti dei test: nessun test chiama un modello vero.

Costerebbe, e risponderebbe ogni volta in un modo diverso. Gli embedding finti sono
coerenti: testi con parole in comune hanno vettori vicini, quindi il recupero dei test
si comporta come quello vero, solo senza Ollama.
"""

import hashlib
import json
import math
import re
from collections.abc import Callable
from typing import Any

import httpx2
from fastapi import Request
from openai import AsyncOpenAI

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
        # zero token, come il ModelloEco del Giorno 4: un finto gratis non scrive nel registro
        return LLMResponse(content=domanda, tokens_used=0, cost_eur=0.0, model="eco")


class ModelloFisso:
    """Un modello che risponde sempre lo stesso testo, deciso dal test."""

    def __init__(self, testo: str) -> None:
        self.testo = testo

    async def complete(self, messages: list[Message], max_tokens: int = 500) -> LLMResponse:
        # 100 token e 0,0001 €, come il ModelloFisso del Giorno 5: dal Giorno 9 il costo si registra
        return LLMResponse(content=self.testo, tokens_used=100, cost_eur=0.0001, model="fisso")


MARCO = UserContext(username="mbianchi", role="operator")  # chi chiede, nei test senza token
GIULIA = UserContext(username="grossi", role="compliance_lead")


def marco_senza_token(request: Request) -> UserContext:
    """Marco come lo restituisce get_current_user, compreso quello che la dependency vera
    scrive nella richiesta: lo username è la chiave del limite di /advice (Giorno 6)."""
    request.state.username = MARCO.username
    return MARCO


def riscrittore_spento() -> QueryRewriter:
    """Il riscrittore dei test che non parlano di riscrittura: la domanda passa com'è."""
    return QueryRewriter(ModelloEco(), "", enabled=False)


# ---- dal Giorno 4: l'SDK di OpenAI vero, con l'API finta a livello HTTP (servono al Giorno 9)
Gestore = Callable[[httpx2.Request], httpx2.Response]


def openai_finto(gestore: Gestore, max_retries: int = 2) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key="sk-test",
        base_url="http://finto/v1",
        max_retries=max_retries,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(gestore)),
    )


def completion(
    testo: str | None,
    *,
    prompt: int = 100,
    uscita: int = 20,
    tool_calls: list[dict[str, Any]] | None = None,
) -> httpx2.Response:
    messaggio: dict[str, Any] = {"role": "assistant", "content": testo}
    if tool_calls:
        messaggio["tool_calls"] = tool_calls
    return httpx2.Response(
        200,
        json={
            "id": "c1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": messaggio,
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt,
                "completion_tokens": uscita,
                "total_tokens": prompt + uscita,
            },
        },
    )


def chiamata(id_: str, nome: str, argomenti: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": id_,
        "type": "function",
        "function": {"name": nome, "arguments": json.dumps(argomenti)},
    }
