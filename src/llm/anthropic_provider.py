from typing import cast

from anthropic import APIError, AsyncAnthropic
from anthropic.types import MessageParam, TextBlock

from src.exceptions import LLMProviderError
from src.llm.types import LLMResponse, Message


class AnthropicProvider:
    PRICING = {
        "claude-haiku-4-5-20251001": (0.000226, 0.001129),
        "claude-sonnet-4-6": (0.00271, 0.01355),
    }

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def complete(self, messages: list[Message], max_tokens: int = 500) -> LLMResponse:
        # Separa system
        system = next((m.content for m in messages if m.role == "system"), None)
        user_messages = cast(
            list[MessageParam], [m.model_dump() for m in messages if m.role != "system"]
        )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system if system else "",
                messages=user_messages,
            )
        except APIError as exc:
            # l'errore dell'SDK diventa quello di dominio: chi chiama non deve conoscere l'SDK
            raise LLMProviderError("anthropic", str(exc)) from exc

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        input_cost, output_cost = self.PRICING[self.model]
        cost_eur = (input_tokens * input_cost + output_tokens * output_cost) / 1000

        return LLMResponse(
            content=next((b.text for b in response.content if isinstance(b, TextBlock)), ""),
            tokens_used=input_tokens + output_tokens,
            cost_eur=cost_eur,
            model=self.model,
        )
