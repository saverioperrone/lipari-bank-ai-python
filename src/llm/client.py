from typing import Protocol
from src.llm.types import Message, LLMResponse


class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], max_tokens: int = 500) -> LLMResponse:
        ...