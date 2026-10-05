"""La misura dell'estensione C: quante volte la cache delle riscritture serve davvero.

    uv run python -m scripts.misura_cache

Trenta richieste costruite sulle dieci domande ellittiche di docs/vibe-coding/G6.md:
ogni domanda tre volte, due identiche e una scritta con maiuscole, spazi o punteggiatura
diversi, come succede allo sportello. La sequenza e' costruita, non presa da un log vero:
dice quanto vale la chiave normalizzata rispetto a quella grezza, non quanto si ripetono
le domande in una filiale.

Alla fine lo stesso deposito viene usato da un riscrittore con il prompt v1: deve tornare
al modello, perche' le riscritture del prompt v2 non valgono per il v1.
"""

import asyncio
import statistics
import time
from pathlib import Path

from pydantic import BaseModel

from src.llm.client import LLMProvider
from src.llm.factory import build_llm_provider
from src.llm.prompt import load_prompt
from src.llm.rewriter import QueryRewriter
from src.llm.types import LLMResponse, Message

USCITA = Path(__file__).parent.parent / "docs" / "eval" / "cache_riscrittura.json"

DOMANDE_ELLITTICHE = [
    "e per l'home banking?",
    "il limite è sempre quello?",
    "contanti 5k, va registrato?",
    "entro quando?",
    "e la segnalazione chi la manda?",
    "prepagata base max?",
    "e per i minorenni?",
    "cliente storico dopo quanto?",
    "e lo sconto quant'è?",
    "carta rubata, dopo il blocco?",
]


def variante(domanda: str) -> str:
    """La stessa domanda come la scrive un altro operatore: maiuscola, spazi, niente '?'."""
    return "  " + domanda[0].upper() + domanda[1:].replace(" ", "  ", 1).rstrip("?") + " "


def sequenza() -> list[str]:
    return [q for d in DOMANDE_ELLITTICHE for q in (d, variante(d), d)]


class ProviderContato:
    """Il provider vero, con il conto delle chiamate che arrivano al modello."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm
        self.chiamate = 0

    async def complete(self, messages: list[Message], max_tokens: int = 500) -> LLMResponse:
        self.chiamate += 1
        return await self.llm.complete(messages, max_tokens)


class Richiesta(BaseModel):
    domanda: str
    riscritta: str
    hit: bool
    hit_chiave_grezza: bool
    ms: float


class MisuraCache(BaseModel):
    richieste: int
    servite_dalla_cache: int
    servite_con_chiave_grezza: int
    chiamate_al_modello: int
    ripieghi_non_salvati: int
    ms_medi_riscrittura_vera: float
    ms_medi_dalla_cache: float
    secondi_con_cache: float
    secondi_stimati_senza_cache: float
    prompt_cambiato_torna_al_modello: bool
    dettaglio: list[Richiesta]


async def main() -> None:
    modello = ProviderContato(build_llm_provider(temperature=0))
    deposito: dict[str, str] = {}
    v2 = QueryRewriter(modello, load_prompt("rewrite_system_v2"), cache=deposito)

    righe: list[Richiesta] = []
    salvate_grezze: set[str] = set()  # le domande esatte la cui riscrittura e' in cache
    for q in sequenza():
        hit = v2.in_cache(q)
        hit_grezzo = q in salvate_grezze
        inizio = time.perf_counter()
        riscritta = await v2.rewrite_cached(q)
        ms = (time.perf_counter() - inizio) * 1000
        if riscritta != q:
            salvate_grezze.add(q)
        righe.append(
            Richiesta(domanda=q, riscritta=riscritta, hit=hit, hit_chiave_grezza=hit_grezzo, ms=ms)
        )

    chiamate_prima = modello.chiamate
    v1 = QueryRewriter(modello, load_prompt("rewrite_system_v1"), cache=deposito)
    await v1.rewrite_cached(DOMANDE_ELLITTICHE[2])
    prompt_cambiato_torna = modello.chiamate == chiamate_prima + 1

    vere = [r.ms for r in righe if not r.hit]
    dalla_cache = [r.ms for r in righe if r.hit]
    misura = MisuraCache(
        richieste=len(righe),
        servite_dalla_cache=len(dalla_cache),
        servite_con_chiave_grezza=sum(r.hit_chiave_grezza for r in righe),
        chiamate_al_modello=chiamate_prima,
        ripieghi_non_salvati=sum(1 for r in righe if not r.hit and r.riscritta == r.domanda),
        ms_medi_riscrittura_vera=statistics.mean(vere),
        ms_medi_dalla_cache=statistics.mean(dalla_cache) if dalla_cache else 0.0,
        secondi_con_cache=sum(r.ms for r in righe) / 1000,
        secondi_stimati_senza_cache=len(righe) * statistics.mean(vere) / 1000,
        prompt_cambiato_torna_al_modello=prompt_cambiato_torna,
        dettaglio=righe,
    )

    print(f"richieste:                         {misura.richieste}")
    print(
        f"servite dalla cache:               {misura.servite_dalla_cache} "
        f"(con la chiave grezza sarebbero state {misura.servite_con_chiave_grezza})"
    )
    print(f"chiamate al modello:               {misura.chiamate_al_modello} (senza cache 30)")
    print(f"ripieghi, non messi in cache:      {misura.ripieghi_non_salvati}")
    print(
        f"una riscrittura vera:              {misura.ms_medi_riscrittura_vera:.0f} ms, "
        f"una dalla cache: {misura.ms_medi_dalla_cache:.2f} ms"
    )
    print(
        f"tempo totale:                      {misura.secondi_con_cache:.1f} s con la cache, "
        f"~{misura.secondi_stimati_senza_cache:.0f} s senza"
    )
    print(f"prompt v1 sullo stesso deposito:   torna al modello = {prompt_cambiato_torna}")

    USCITA.parent.mkdir(parents=True, exist_ok=True)
    USCITA.write_text(misura.model_dump_json(indent=2), encoding="utf-8")
    print("scritto docs/eval/cache_riscrittura.json")


if __name__ == "__main__":
    asyncio.run(main())
