"""Fondere due elenchi ordinati che non hanno lo stesso metro.

La ricerca vettoriale da' una similarita' coseno, la ricerca lessicale un `ts_rank_cd`:
il primo sta fra 0 e 1, il secondo cresce con quante volte e quanto vicine compaiono le
parole cercate. Sommarli, o normalizzarli e poi sommarli, vuol dire decidere a caso
quanto pesa una ricerca rispetto all'altra.

La fusione per rango non li guarda proprio, i punteggi: guarda solo in che posizione
ogni passaggio e' arrivato in ciascun elenco. Un passaggio primo in un elenco e assente
nell'altro batte un passaggio quinto in tutti e due, e nessuna delle due scale entra nel
conto.
"""

from collections.abc import Callable, Hashable

COSTANTE = 60.0
"""Quanto conta essere primi invece che terzi.

Con 60 le prime posizioni valgono poco piu' delle successive, e serve comparire in
entrambi gli elenchi per salire davvero; con un numero piccolo, 1 o 2, il primo posto
di un elenco solo schiaccia tutto il resto. Il 60 e' il valore del lavoro che ha
proposto questo metodo, tenuto perche' le dieci domande non bastano a tararne uno.
"""


def fondi[T](elenchi: list[list[T]], chiave: Callable[[T], Hashable]) -> list[T]:
    """Un solo elenco ordinato, a partire da piu' elenchi gia' ordinati.

    `chiave` dice quando due elementi di elenchi diversi sono lo stesso passaggio.
    """
    punteggi: dict[Hashable, float] = {}
    primo_incontro: dict[Hashable, T] = {}
    for elenco in elenchi:
        for posizione, elemento in enumerate(elenco, start=1):
            id_ = chiave(elemento)
            punteggi[id_] = punteggi.get(id_, 0.0) + 1.0 / (COSTANTE + posizione)
            primo_incontro.setdefault(id_, elemento)

    ordinati = sorted(punteggi, key=lambda id_: punteggi[id_], reverse=True)
    return [primo_incontro[id_] for id_ in ordinati]
