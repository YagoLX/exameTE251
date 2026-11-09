#!/usr/bin/env python3
"""
experimento_recall.py - mede o retrieval contra um conjunto adversarial.

Dez consultas com gabarito definido A MAO antes de rodar, cada uma em portugues e
em ingles. Mede, por backend e por lingua:

  recall@k  - em quantas consultas o artigo-ouro aparece entre os k devolvidos
  top1      - em quantas o artigo-ouro e o primeiro
  curto     - em quantas o top-1 e um chunk de cabecalho (< 40 caracteres)
  zero      - em quantas TODOS os scores sao 0 (nenhuma sobreposicao)

Uso:
    python experimento_recall.py                       # backend tfidf
    python experimento_recall.py --backend e5
    python experimento_recall.py --backend e5 --csv resultados_e5.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buscar_artigo import Indice  # noqa: E402

# (id, pergunta em portugues, pergunta em ingles, artigos aceitos como ouro)
CONSULTAS = [
    ("q01", "pode rocar estando em xeque?",
     "may a player castle while the king is in check", ["3.8.2.2"]),
    ("q02", "pode rocar se o rei atravessa uma casa atacada?",
     "may a player castle if the square the king crosses is attacked", ["3.8.2.2"]),
    ("q03", "pode rocar se a torre esta atacada?",
     "may a player castle if the rook is attacked", ["3.8.2.2"]),
    ("q04", "pode rocar depois que o rei ja mexeu?",
     "may a player castle after the king has already moved", ["3.8.2.1"]),
    ("q05", "o que diz o artigo 3.8.2.1?",
     "what does article 3.8.2.1 say", ["3.8.2.1"]),
    ("q06", "e permitido deixar o proprio rei em xeque?",
     "may a player leave their own king in check", ["3.9.2"]),
    ("q07", "um lance ilegal foi completado, e agora?",
     "what happens when an illegal move has been completed", ["7.5.1", "7.5"]),
    ("q08", "quando a captura en passant e possivel?",
     "when is an en passant capture possible", ["3.7.3.1", "3.7.3.2"]),
    ("q09", "para quais pecas um peao pode promover?",
     "which pieces may a pawn promote to", ["3.7.3.3"]),
    ("q10", "o que e uma posicao morta?",
     "what is a dead position", ["5.2.2"]),
]

CURTO = 40  # um chunk com menos que isto e cabecalho de clausula-pai


def rodar(idx: Indice, k: int, lingua: str) -> tuple[list[dict], dict]:
    curtos = {c["artigo"] for c in idx.chunks if len(c["texto"]) < CURTO}
    linhas, agg = [], {"top1": 0, "recall": 0, "curto": 0, "zero": 0}

    for qid, pt, en, ouro in CONSULTAS:
        consulta = pt if lingua == "pt" else en
        hits = idx.buscar(consulta, k=k)
        arts = [h["artigo"] for h in hits]
        scores = [h["score"] for h in hits]

        top1 = arts[0] in ouro
        recall = any(a in ouro for a in arts)
        curto = arts[0] in curtos
        zero = all(s == 0 for s in scores)

        agg["top1"] += top1
        agg["recall"] += recall
        agg["curto"] += curto
        agg["zero"] += zero

        linhas.append({
            "id": qid, "lingua": lingua, "consulta": consulta,
            "ouro": "|".join(ouro), "top_k": "|".join(arts),
            "score_top1": scores[0],
            "top1": int(top1), "recall_k": int(recall),
            "top1_curto": int(curto), "score_zero": int(zero),
        })
    return linhas, agg


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", default="tfidf", choices=["tfidf", "e5"])
    p.add_argument("-k", type=int, default=3)
    p.add_argument("--csv", help="grava as linhas num CSV")
    a = p.parse_args()

    idx = Indice.carregar(a.backend)
    n = len(CONSULTAS)
    todas = []

    print(f"backend={a.backend}  k={a.k}  chunks={len(idx.chunks)}  consultas={n}\n")
    for lingua in ("en", "pt"):
        linhas, agg = rodar(idx, a.k, lingua)
        todas += linhas
        print(f"=== {lingua.upper()} ===")
        for l in linhas:
            marca = "OK" if l["top1"] else ("~ " if l["recall_k"] else "--")
            alerta = " [cabecalho]" if l["top1_curto"] else ""
            alerta += " [score 0]" if l["score_zero"] else ""
            print(f"  {marca} {l['id']}  ouro={l['ouro']:<16} top{a.k}={l['top_k']}{alerta}")
        print(f"  --> top1 {agg['top1']}/{n} | recall@{a.k} {agg['recall']}/{n} "
              f"| top1 e cabecalho {agg['curto']}/{n} | score zero {agg['zero']}/{n}\n")

    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(todas[0].keys()))
            w.writeheader()
            w.writerows(todas)
        print(f"CSV: {a.csv}")


if __name__ == "__main__":
    main()