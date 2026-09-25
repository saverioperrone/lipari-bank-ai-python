from openai import AsyncOpenAI

from src.llm.types import Message, LLMResponse


class OllamaProvider:
    """Modello servito in locale da Ollama.

    Ollama espone un endpoint compatibile con le API OpenAI, quindi riusa lo
    stesso client: cambia solo `base_url`. Il costo e' zero perche' gira in
    locale, ma i token vengono contati lo stesso, ed e' su quelli che si
    proietta la spesa di un modello a pagamento.
    """

    PRICING = {}  # nessun costo: modello locale

    def __init__(self, base_url: str, model: str = "llama3.2:3b") -> None:
        self.client = AsyncOpenAI(api_key="ollama", base_url=base_url)
        self.model = model

    async def complete(self, messages: list[Message], max_tokens: int = 500) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[m.model_dump() for m in messages],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        usage = response.usage
        total_tokens = usage.total_tokens if usage else 0

        return LLMResponse(
            content=response.choices[0].message.content or "",
            tokens_used=total_tokens,
            cost_eur=0.0,
            model=self.model,
        )
