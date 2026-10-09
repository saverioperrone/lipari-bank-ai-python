# evals/confronto.py — estensione 3: gli esiti caso per caso, confrontati con l'esecuzione prima
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

# Il sottoinsieme congelato: id e impronta dei casi scritti il Giorno 9. È versionato e non si
# riscrive: un caso aggiunto dopo non ci entra, e uno modificato ne esce da solo
CONGELATO = Path(__file__).parent / "datasets" / "congelato.json"


class Esito(TypedDict):
    ok: bool
    errore: bool  # caduto per un'eccezione, del fornitore o del database: non è stato misurato
    impronta: str
    nota: str


def impronta(caso: dict[str, Any]) -> str:
    """L'input e la risposta attesa, non la nota: riscrivere un commento non cambia il caso."""
    materiale = json.dumps([caso["input"], caso["expected"]], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(materiale.encode()).hexdigest()[:12]


def esiti_dei_casi(
    casi: list[dict[str, Any]], falliti: set[str], errori: frozenset[str] = frozenset()
) -> dict[str, Esito]:
    """Ogni caso del dataset, giusto o sbagliato: i fallimenti del runner dicono quali."""
    return {
        c["id"]: {
            "ok": c["id"] not in falliti,
            "errore": c["id"] in errori,
            "impronta": impronta(c),
            "nota": c.get("nota", ""),
        }
        for c in casi
    }


@dataclass
class Confronto:
    nome: str
    congelati: int  # i casi del sottoinsieme congelato, uguali nelle due esecuzioni
    giusti_prima: int  # quanti di quelli erano giusti nell'esecuzione precedente
    giusti_adesso: int
    peggiorati: list[str]  # da giusti a sbagliati
    migliorati: list[str]  # da sbagliati a giusti
    fuori: list[str]  # nuovi, cambiati con lo stesso id o caduti per un errore: non si confrontano
    usciti: list[str]  # congelati cambiati o tolti dal dataset: il metro che si accorcia


def confronta(
    nome: str, prima: dict[str, Esito], adesso: dict[str, Esito], congelato: dict[str, str]
) -> Confronto:
    # per id, ma solo i casi rimasti uguali e misurati tutte e due le volte: un caso riscritto è
    # un altro caso con lo stesso nome, e uno caduto per un errore non è un peggioramento
    comuni = [
        i
        for i in adesso
        if i in prima
        and prima[i]["impronta"] == adesso[i]["impronta"]
        and not (prima[i]["errore"] or adesso[i]["errore"])
    ]
    # l'aggregato solo sui congelati: con dei casi in più, quello intero è un metro più lungo
    stabili = [i for i in comuni if congelato.get(i) == adesso[i]["impronta"]]
    return Confronto(
        nome=nome,
        congelati=len(stabili),
        giusti_prima=sum(prima[i]["ok"] for i in stabili),
        giusti_adesso=sum(adesso[i]["ok"] for i in stabili),
        peggiorati=[i for i in comuni if prima[i]["ok"] and not adesso[i]["ok"]],
        migliorati=[i for i in comuni if adesso[i]["ok"] and not prima[i]["ok"]],
        fuori=[i for i in adesso if i not in comuni],
        usciti=[
            i
            for i, firma in congelato.items()
            if (i in prima or i in adesso) and (i not in adesso or adesso[i]["impronta"] != firma)
        ],
    )


def rapporto_confronto(
    confronti: list[Confronto], quando: str, adesso: dict[str, dict[str, Esito]]
) -> str:
    righe = [f"confronto con l'esecuzione del {quando}:"]
    for c in confronti:
        righe.append(
            f"{c.nome:12} sui {c.congelati} congelati: giusti prima {c.giusti_prima}, "
            f"adesso {c.giusti_adesso}"
        )
        for titolo, ids in (
            ("da giusto a sbagliato", c.peggiorati),
            ("da sbagliato a giusto", c.migliorati),
        ):
            # con la nota: fra un mese l'id da solo non ricorda più di che caso si tratta
            righe.extend(f"    {titolo}: {i} ({adesso[c.nome][i]['nota']})" for i in ids)
        if c.fuori:
            righe.append(f"    fuori dal confronto, nuovi, cambiati o caduti: {', '.join(c.fuori)}")
        if c.usciti:
            righe.append(f"    congelati che non valgono più: {', '.join(c.usciti)}")
    return "\n".join(righe)


def carica(percorso: Path) -> dict[str, Any] | None:
    """L'esecuzione precedente, se c'è: la prima volta non c'è niente da confrontare."""
    if not percorso.exists():
        return None
    dati: dict[str, Any] = json.loads(percorso.read_text(encoding="utf-8"))
    return dati


def salva(percorso: Path, esiti: dict[str, dict[str, Esito]]) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    quando = datetime.now(UTC).isoformat(timespec="minutes")
    percorso.write_text(
        json.dumps({"quando": quando, "esiti": esiti}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def congela() -> None:
    """Il sottoinsieme congelato si scrive una volta: riscritto, non sarebbe più congelato."""
    if CONGELATO.exists():
        raise SystemExit(f"{CONGELATO} c'è già: congelato vuol dire che non si riscrive.")
    casi = [
        json.loads(r)
        for f in sorted(CONGELATO.parent.glob("*.jsonl"))
        for r in f.read_text(encoding="utf-8").splitlines()
        if r.strip()
    ]
    CONGELATO.write_text(
        json.dumps({c["id"]: impronta(c) for c in casi}, indent=1) + "\n", encoding="utf-8"
    )
    print(f"{len(casi)} casi congelati in {CONGELATO}")


if __name__ == "__main__":
    congela()
