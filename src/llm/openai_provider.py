from openai import AsyncOpenAI

from src.llm.types import Message, LLMResponse


class OpenAIProvider:
    PRICING = {  # EUR per 1k tokens (input/output)
        "gpt-4o-mini": (0.00014, 0.00056),
        "gpt-4o": (0.0023, 0.0091),
    }

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def complete(self, messages: list[Message], max_tokens: int = 500) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[m.model_dump() for m in messages],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        input_cost, output_cost = self.PRICING[self.model]
        cost_eur = (input_tokens * input_cost + output_tokens * output_cost) / 1000

        return LLMResponse(
            content=response.choices[0].message.content or "",
            tokens_used=response.usage.total_tokens,
            cost_eur=cost_eur,
            model=self.model,
        )