"""Dieci domande vere all'agente, come Marco: quanti passi usa, e quanto sbaglia la stima.

    uv run python -m scripts.misura_agente

Due misure in una. La prima serve a scegliere MAX_STEPS: i passi che l'agente usa
davvero, con un tetto alto apposta, perché il tetto di oggi non tagli la distribuzione.
La seconda è il numero dell'estensione 2: per ogni chiamata al modello, i token che il
loop stima prima di spedirla contro quelli che il modello conta dopo averla letta.

Il modello è quello di DEFAULT_MODEL e il database quello del .env: i tool leggono i
dati del seed, e una segnalazione aperta da una domanda resta aperta. Il risultato
finisce in docs/eval/agente_g7.json.
"""

import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from openai import AsyncOpenAI, Omit
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam, ChatCompletionToolParam

from src.agents.deps import Deps
from src.agents.loop import run_agent, token_stimati
from src.agents.prompts import AGENT_SYSTEM
from src.agents.tools import build_tools_for
from src.auth.deps import UserContext
from src.config import settings
from src.db.repos import AccountRepository, MovementRepository
from src.db.session import AsyncSessionLocal
from src.llm.factory import get_embedder, get_openai
from src.services.alerts import AlertService
from src.services.retrieval_service import RetrievalService

MARCO = UserContext(username="mbianchi", role="operator")
TETTO_DELLA_MISURA = 20  # alto apposta: la misura deve vedere i passi, non il tetto di oggi
USCITA = Path("docs/eval/agente_g7.json")

DOMANDE = [  # (domanda, gruppo)
    ("Qual è il saldo del conto principale del cliente C-10234?", "semplice"),
    ("Quali conti ha il cliente C-10234?", "semplice"),
    ("Quanto c'è sul conto di risparmio del cliente C-10234?", "semplice"),
    ("Mostrami gli ultimi movimenti del conto principale del cliente C-10234.", "semplice"),
    ("Qual è la soglia per un bonifico verso un paese a rischio elevato?", "semplice"),
    ("Cosa devo dire al cliente quando un bonifico verso Panama va in verifica?", "semplice"),
    ("Il saldo del conto principale del cliente C-10234 basta per un bonifico di 50.000 euro?",
     "semplice"),
    ("Il cliente C-10234 ha fatto bonifici verso Panama nell'ultimo mese?", "più tool"),
    ("Il cliente C-10234 vuole fare un bonifico di 25.000 euro verso il Venezuela dal conto "
     "principale: posso procedere?", "più tool"),
    ("Il cliente C-10234 vuole mandare 12.000 euro a Panama dal conto principale: va aperta "
     "una segnalazione? Se serve, aprila.", "più tool"),
]


class Contatore:
    """Il client vero, con una spia: prima della chiamata la stima, dopo il conteggio vero."""

    def __init__(self, vero: AsyncOpenAI) -> None:
        self.vero = vero
        self.chat = self  # il loop chiama client.chat.completions.create
        self.completions = self
        self.chiamate: list[dict[str, int]] = []

    async def create(
        self,
        *,
        model: str,
        messages: list[ChatCompletionMessageParam],
        max_tokens: int,
        tools: list[ChatCompletionToolParam] | Omit,
    ) -> ChatCompletion:
        schemi = tools if isinstance(tools, list) else []
        stimati = token_stimati(messages, schemi)
        caratteri = len(json.dumps([messages, schemi], ensure_ascii=False))
        risposta = await self.vero.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, tools=tools
        )
        contati = risposta.usage.prompt_tokens if risposta.usage else 0
        self.chiamate.append({"caratteri": caratteri, "stimati": stimati, "contati": contati})
        return risposta


async def una_domanda(domanda: str) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        deps = Deps(
            accounts=AccountRepository(session),
            movements=MovementRepository(session),
            alerts=AlertService(session),
            retrieval=RetrievalService(session),
            embedder=get_embedder(),
            openai=get_openai(),
            model=settings.default_model,
        )
        spia = Contatore(deps.openai)
        run = await run_agent(
            messaggi=[
                {"role": "system", "content": AGENT_SYSTEM},
                {"role": "user", "content": domanda},
            ],
            tools=build_tools_for(MARCO, deps),
            client=cast(AsyncOpenAI, spia),
            model=deps.model,
            max_steps=TETTO_DELLA_MISURA,
        )
    return {
        "steps": run.steps,
        "tool_calls": run.tool_calls,
        "stopped_by": run.stopped_by,
        "chiamate": spia.chiamate,
        "reply": run.reply,
    }


async def main() -> None:
    risultati = []
    for domanda, gruppo in DOMANDE:
        esito = await una_domanda(domanda)
        risultati.append({"domanda": domanda, "gruppo": gruppo, **esito})
        print(f"{esito['steps']:>2} passi  {esito['stopped_by']:<9} {esito['tool_calls']}")
        print(f"          {domanda}")

    chiamate = [c for r in risultati for c in r["chiamate"]]
    rapporti = [c["stimati"] / c["contati"] for c in chiamate if c["contati"]]
    per_token = [c["caratteri"] / c["contati"] for c in chiamate if c["contati"]]
    sotto = sum(1 for c in chiamate if c["stimati"] < c["contati"])
    passi = Counter(r["steps"] for r in risultati)
    sintesi = {
        "modello": settings.default_model,
        "distribuzione_passi": dict(sorted(passi.items())),
        "chiamate": len(chiamate),
        "stima_su_contati": {
            "min": round(min(rapporti), 2),
            "media": round(sum(rapporti) / len(rapporti), 2),
            "max": round(max(rapporti), 2),
        },
        "caratteri_per_token": {
            "min": round(min(per_token), 2),
            "media": round(sum(per_token) / len(per_token), 2),
            "max": round(max(per_token), 2),
        },
        "chiamate_sottostimate": sotto,
    }
    print(json.dumps(sintesi, ensure_ascii=False, indent=2))
    testo = json.dumps({"sintesi": sintesi, "domande": risultati}, ensure_ascii=False, indent=2)
    # scrivere un file è bloccante: dentro una coroutine si sposta su un thread
    await asyncio.to_thread(USCITA.write_text, testo, encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
