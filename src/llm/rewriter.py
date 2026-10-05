import hashlib
import logging

from src.llm.client import LLMProvider
from src.llm.types import Message

log = logging.getLogger(__name__)


class QueryRewriter:
    """Porta la domanda dell'utente in una forma che il recupero sa cercare."""

    # il provider va costruito con temperature 0: è una traduzione, non una risposta
    def __init__(self, llm: LLMProvider, prompt: str, enabled: bool = True) -> None:
        self.llm = llm
        self.prompt = prompt
        self.enabled = enabled
        self._cache: dict[str, str] = {}

    async def rewrite(self, question: str, history: list[str] | None = None) -> str:
        """Riformula la domanda in una forma che il recupero può cercare.

        Se il modello non risponde o risponde male, ritorna la domanda originale:
        una riscrittura mancata non deve impedire una risposta.
        """
        if not self.enabled:
            return question
        coda = "\n".join(history[-3:]) if history else ""
        try:
            risposta = await self.llm.complete(
                [
                    Message(role="system", content=self.prompt),
                    Message(role="user", content=f"{coda}\n\nDomanda: {question}".strip()),
                ],
                max_tokens=80,
            )
        except Exception:
            log.warning("rewriter.fallito", extra={"domanda": question})
            return question

        riscritta = risposta.content.strip().strip('"')
        # una riscrittura vuota, o molto più lunga della domanda, è una risposta
        # travestita: si scarta, e il recupero prosegue sull'originale
        if not riscritta or len(riscritta) > 4 * len(question) + 80:
            log.warning("rewriter.scartata", extra={"uscita": riscritta[:120]})
            return question
        return riscritta

    async def rewrite_cached(self, question: str) -> str:
        key = f"rewrite:{hashlib.sha256(question.encode()).hexdigest()}"
        if (cached := self._cache.get(key)) is not None:
            return cached
        result = await self.rewrite(question)
        # il ripiego non si salva: quando il modello torna, la domanda si riscrive davvero
        if result != question:
            self._cache[key] = result
        return result
