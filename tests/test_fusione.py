"""La proprieta' dichiarata: un passaggio che la ricerca vettoriale non ha visto
affatto puo' entrare nei primi k, se la ricerca lessicale lo ha messo in cima.

E' il motivo per cui la ricerca ibrida e' stata scritta — hit@5 da 8/10 a 10/10 sulle
dieci domande — e la fusione per rango e' il pezzo che lo rende possibile. Se questo
test fallisce, la fusione sta restituendo l'ordine di uno solo dei due elenchi, e
l'estensione non serve piu' a niente.
"""

from src.lib.fusione import fondi


def test_la_fusione_fa_entrare_un_passaggio_che_il_vettore_non_aveva() -> None:
    vettoriale = ["a", "b", "c", "d", "e"]
    lessicale = ["x", "a", "f", "g", "h"]

    fusi = fondi([vettoriale, lessicale], chiave=lambda p: p)

    assert "x" not in vettoriale, "il caso ha senso solo se il vettore non lo aveva visto"
    assert "x" in fusi[:5]
    assert fusi[0] == "a", "chi compare in tutti e due gli elenchi sta davanti"
