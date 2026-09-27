"""Riconoscere due passaggi che dicono la stessa cosa.

Serve perche' i PDF uniti a mano ripetono pagine, e una pagina ripetuta non produce
chunk identici: il taglio cade in punti diversi nelle due copie, quindi l'hash del
contenuto non vede niente. Quello che resta uguale sono le sequenze di parole.

Il numero di `SOGLIA_SOVRAPPOSIZIONE` e' misurato su questo corpus, non scelto.
Confrontando tutte le coppie di passaggi documento per documento: nelle tre circolari
senza ripetizioni la coppia piu' sovrapposta sta a 0,23, ed e' la sovrapposizione voluta
del chunking; nella circolare con la pagina ripetuta le coppie duplicate stanno fra 0,49
e 0,97. Fra 0,23 e 0,49 non c'e' niente, e 0,40 sta in mezzo a quel vuoto.
"""

import re
from collections.abc import Callable

SOGLIA_SOVRAPPOSIZIONE = 0.40
LUNGHEZZA_SEQUENZA = 5


def sequenze(testo: str, n: int = LUNGHEZZA_SEQUENZA) -> set[tuple[str, ...]]:
    """Le sequenze di n parole del testo, normalizzate.

    Si guarda alle sequenze e non alle singole parole perche' due paragrafi dello
    stesso documento condividono quasi tutto il vocabolario senza dirsi la stessa cosa.
    """
    parole = re.findall(r"\w+", testo.lower())
    return {tuple(parole[i:i + n]) for i in range(max(0, len(parole) - n + 1))}


def sovrapposizione(a: str, b: str) -> float:
    """Quanta parte del piu' corto dei due sta anche nel piu' lungo, fra 0 e 1.

    Contenimento e non Jaccard: una pagina ripetuta produce pezzi di lunghezza diversa,
    e Jaccard punirebbe la differenza di lunghezza proprio nel caso da riconoscere.
    """
    sa, sb = sequenze(a), sequenze(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def senza_ripetizioni[T](candidati: list[T], quanti: int, testo: Callable[[T], str]) -> list[T]:
    """I primi `quanti` elementi, saltando quelli che ridicono un elemento gia' tenuto.

    Una pagina ripetuta nel PDF occupava tre dei cinque posti del contesto con lo stesso
    testo, e usciva come tre citazioni distinte: la stessa cosa detta una volta sola con
    l'aria di tre conferme indipendenti.
    """
    tenuti: list[T] = []
    for c in candidati:
        if any(sovrapposizione(testo(c), testo(t)) >= SOGLIA_SOVRAPPOSIZIONE for t in tenuti):
            continue
        tenuti.append(c)
        if len(tenuti) == quanti:
            break
    return tenuti
