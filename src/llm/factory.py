from src.config import settings
from src.llm.client import LLMProvider
from src.llm.openai_provider import OpenAIProvider
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.ollama_provider import OllamaProvider

# Prefissi dei modelli serviti da Ollama in locale.
OLLAMA_PREFIXES = ("llama", "qwen", "mistral", "gemma", "phi")


def get_llm_provider(model: str | None = None) -> LLMProvider:
    selected = model or settings.default_model
    if selected.startswith("gpt"):
        return OpenAIProvider(settings.openai_api_key, selected)
    elif selected.startswith("claude"):
        return AnthropicProvider(settings.anthropic_api_key, selected)
    elif selected.startswith(OLLAMA_PREFIXES):
        return OllamaProvider(settings.ollama_base_url, selected)
    else:
        raise ValueError(f"Unknown model: {selected}")