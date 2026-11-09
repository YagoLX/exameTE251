#!/usr/bin/env python3
"""
comparador.py - o unico ponto em que os dois ramos se encontram. Codigo, sem IA.

comparar(resposta_a, resultado_b) -> {"parada": ..., "motivo": ...}
  parada in {"concordam", "discordam", "erro", "recusa"}

  resposta_a   dict ja parseado do JSON do Ramo A, ou None se nao parseou
  resultado_b  saida de legalidade(fen, lance), ou None se a pergunta nao tem FEN

Pergunta sem FEN NAO passa por aqui: nao ha o que comparar, e o agente marca
`sem_verificacao` antes. "Concordam" so diz que os ramos bateram, nao que
estao certos (busca errada + veredito certo por coincidencia tambem concorda).

Uso:  python src/comparador.py --demo     # dispara as quatro paradas
"""
from __future__ import annotations

import re

RECUSA = "nao consta no material"

# Sem lance: o Ramo A responde em texto curto. Estas sao as respostas aceitas
# para cada estado do Ramo B, escritas para as perguntas da suite (c21-c23).
# E uma regra de casamento declarada, nao um juiz: o que nao casar e discordancia.
ACEITA_SEM_LANCE = {
    "afogado": {"no", "stalemate"},
    "posicao_morta": {"no", "dead position"},
    "cinquenta_lances": {"yes", "draw"},
    "mate": {"yes", "checkmate"},
}


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", str(s).lower().replace("ã", "a")).strip()


def comparar(resposta_a: dict | None, resultado_b: dict | None) -> dict:
    if resultado_b is None:
        raise ValueError("pergunta sem FEN nao vai ao comparador (sem_verificacao)")
    if not isinstance(resposta_a, dict) or "veredito" not in resposta_a:
        return {"parada": "erro", "motivo": "Ramo A sem JSON valido com 'veredito'"}
    if resultado_b.get("veredito") == "erro":
        return {"parada": "erro", "motivo": f"Ramo B: {resultado_b.get('motivo')}"}

    a, b = _norm(resposta_a["veredito"]), resultado_b["veredito"]
    if a == RECUSA:
        return {"parada": "recusa", "motivo": "Ramo A: nao consta no material"}

    if resultado_b.get("lance"):
        bate = a == b
    elif b.endswith("_lances") and b[0].isdigit():
        bate = b.split("_")[0] in a.split()
    else:
        palavras = a.split()
        bate = any(x in palavras[:1] or (" " in x and x in a)
                   for x in ACEITA_SEM_LANCE.get(b, set()))
    return {"parada": "concordam" if bate else "discordam",
            "motivo": f"A={resposta_a['veredito']!r} B={b!r}"}


def _demo() -> None:
    b_legal = {"fen": "x", "lance": "e1c1", "veredito": "legal"}
    casos = [
        ("concordam", {"veredito": "legal"}, b_legal),
        ("discordam", {"veredito": "ilegal"}, b_legal),
        ("erro", None, b_legal),
        ("erro", {"veredito": "legal"}, {"lance": "zz", "veredito": "erro", "motivo": "lance imparsavel"}),
        ("recusa", {"veredito": "nao consta no material"}, b_legal),
        ("concordam", {"veredito": "No, it is stalemate"}, {"lance": None, "veredito": "afogado"}),
        ("discordam", {"veredito": "Yes"}, {"lance": None, "veredito": "afogado"}),
        ("concordam", {"veredito": "23"}, {"lance": None, "veredito": "23_lances"}),
    ]
    falhas = 0
    for esperado, a, b in casos:
        r = comparar(a, b)
        falhas += r["parada"] != esperado
        print(f"  {'ok ' if r['parada'] == esperado else 'FALHA'} {r['parada']:<10} {r['motivo']}")
    raise SystemExit(1 if falhas else 0)


if __name__ == "__main__":
    _demo()
