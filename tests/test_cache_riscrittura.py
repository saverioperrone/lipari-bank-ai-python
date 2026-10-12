"""La proprieta' dichiarata dall'estensione C, in un test solo.

Le varianti di scrittura della stessa domanda sono una riscrittura sola, e un prompt
nuovo non riceve le riscritture del vecchio, nemmeno quando il deposito e' lo stesso.
"""

import fakeredis

from src.llm.rewriter import QueryRewriter
from src.llm.types import LLMResponse, Message


class ModelloContato:
    def __init__(self) -> None:
        self.chiamate = 0

    async def complete(self, messages: list[Message], max_tokens: int = 500) -> LLMResponse:
        self.chiamate += 1
        riscritta = "Le operazioni verso il Venezuela sono consentite?"
        return LLMResponse(content=riscritta, tokens_used=1, cost_eur=0.0, model="contato")


async def test_la_chiave_unisce_le_varianti_e_cambia_con_il_prompt() -> None:
    # dal Giorno 10 il deposito condiviso è Redis: qui uno in memoria, lo stesso per i due prompt
    deposito = fakeredis.FakeServer()
    modello = ModelloContato()
    v1 = QueryRewriter(modello, "prompt v1", cache=fakeredis.FakeAsyncRedis(server=deposito))
    prima = await v1.rewrite_cached("ven ok?")
    assert await v1.rewrite_cached("  Ven  OK ") == prima  # la variante esce dalla cache
    assert modello.chiamate == 1

    # stesso deposito, prompt nuovo
    v2 = QueryRewriter(modello, "prompt v2", cache=fakeredis.FakeAsyncRedis(server=deposito))
    await v2.rewrite_cached("ven ok?")
    assert modello.chiamate == 2  # la riscrittura del v1 non viene servita al v2
