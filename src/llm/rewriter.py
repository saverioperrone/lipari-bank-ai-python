import hashlib
import logging

from src.llm.client import LLMProvider
from src.llm.types import Message

log = logging.getLogger(__name__)


def normalizza(domanda: str) -> str:
    """La forma della domanda che decide la chiave della cache.

    Minuscole, spazi singoli, senza la punteggiatura finale: «Ven OK ?» e «ven ok» sono
    la stessa domanda, e allo sportello si scrivono tutte e due.
    """
    return " ".join(domanda.lower().split()).rstrip("?!. ")


class QueryRewriter:
    """Porta la domanda dell'utente in una forma che il recupero sa cercare."""

    # il provider va costruito con temperature 0: è una traduzione, non una risposta
    def __init__(
        self,
        llm: LLMProvider,
        prompt: str,
        enabled: bool = True,
        cache: dict[str, str] | None = None,
    ) -> None:
        self.llm = llm
        self.prompt = prompt
        self.enabled = enabled
        # il deposito si puo' passare da fuori: oggi e' un dict del processo, domani uno
        # condiviso fra i worker, e un deposito condiviso sopravvive al cambio di prompt
        self._cache: dict[str, str] = {} if cache is None else cache

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

    def _chiave(self, question: str) -> str:
        """Il prompt e la domanda normalizzata: la riscrittura dipende da tutti e due.

        Con il prompt dentro la chiave, un prompt nuovo non riceve le riscritture del
        vecchio anche quando il deposito e' lo stesso: le sue chiavi sono altre.
        """
        materiale = f"{self.prompt}\x00{normalizza(question)}"
        return f"rewrite:{hashlib.sha256(materiale.encode()).hexdigest()}"

    def in_cache(self, question: str) -> bool:
        return self._chiave(question) in self._cache

    async def rewrite_cached(self, question: str) -> str:
        key = self._chiave(question)
        if (cached := self._cache.get(key)) is not None:
            return cached
        result = await self.rewrite(question)
        # il ripiego non si salva: quando il modello torna, la domanda si riscrive davvero
        if result != question:
            self._cache[key] = result
        return result
