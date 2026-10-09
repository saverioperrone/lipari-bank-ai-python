from functools import cache

import instructor
from openai import AsyncOpenAI

from src.config import settings
from src.exceptions import AppError
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.client import LLMProvider
from src.llm.embedding_client import EmbeddingClient
from src.llm.ollama_provider import OllamaProvider
from src.llm.openai_provider import OpenAIProvider

# Prefissi dei modelli serviti da Ollama in locale.
OLLAMA_PREFIXES = ("llama", "qwen", "mistral", "gemma", "phi")


def build_llm_provider(model: str | None = None, temperature: float = 0.3) -> LLMProvider:
    selected = model or settings.default_model
    if selected.startswith("gpt"):
        return OpenAIProvider(settings.openai_api_key, selected, temperature)
    elif selected.startswith("claude"):
        return AnthropicProvider(settings.anthropic_api_key, selected)
    elif selected.startswith(OLLAMA_PREFIXES):
        return OllamaProvider(settings.ollama_base_url, selected, temperature)
    else:
        raise ValueError(f"Unknown model: {selected}")


def get_llm_provider() -> LLMProvider:
    """Il provider degli endpoint. Senza parametri: FastAPI non li pubblica nella query."""
    return build_llm_provider()


embedding_client = EmbeddingClient()


def get_embedder() -> EmbeddingClient:
    return embedding_client  # istanza unica di applicazione


def _client_dell_agente() -> AsyncOpenAI | None:
    """L'SDK di OpenAI per il modello in uso, con la stessa regola di `build_llm_provider`.

    Un modello locale parla con Ollama, che espone la stessa API: cambia solo l'indirizzo,
    e la chiave non serve. Gli altri parlano con OpenAI, e senza chiave il client non c'è.
    """
    if settings.default_model.startswith(OLLAMA_PREFIXES):
        return AsyncOpenAI(api_key="ollama", base_url=settings.ollama_base_url)
    if not settings.openai_api_key:
        return None
    return AsyncOpenAI(api_key=settings.openai_api_key)


openai_client = _client_dell_agente()


def get_openai() -> AsyncOpenAI:
    """Il client dell'agente: uno per processo, come l'embedder."""
    if openai_client is None:
        raise AppError(503, "API_KEY_MISSING", "Manca OPENAI_API_KEY: l'agente non può partire")
    return openai_client


@cache
def get_instructor() -> instructor.AsyncInstructor:
    # Il client è quello di get_openai, con la regola di build_llm_provider. Con un modello
    # di Ollama il modo è JSON: in modo TOOLS llama3.2:3b sbaglia lo schema (G4, e rimisurato
    # al G9: 1 categorizzazione su 2 in TOOLS, 2 su 2 in JSON)
    modo = (
        instructor.Mode.JSON
        if settings.default_model.startswith(OLLAMA_PREFIXES)
        else instructor.Mode.TOOLS
    )
    return instructor.from_openai(get_openai(), mode=modo)
