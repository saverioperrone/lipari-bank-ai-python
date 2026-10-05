from src.config import settings
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
