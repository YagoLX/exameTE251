#!/usr/bin/env python3
"""
checar_trechos.py - planilha para a checagem HUMANA dos trechos recuperados.

Para cada caso da suite: consulta (= pergunta), top-k (artigo + texto), e se
algum artigo_ouro esta no top-k (calculado em codigo, por prefixo: ouro 3.8.2
casa com 3.8.2.2 recuperado e vice-versa NAO; so o recuperado igual ou mais
especifico que o ouro conta). O rotulo humano dos trechos (suficiente / parcial /
ausente) fica em resultados/rotulos_humanos.json, gravado pela interface.

Uso:
    python src/checar_trechos.py                  # resultados/checagem_trechos_tfidf_k3.csv
    python src/checar_trechos.py --backend e5 -k 3
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buscar_artigo import Indice, E5_MODELO  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SUITE = RAIZ / "suite" / "suite_30.jsonl"


def ouro_no_topk(ouros: list[str], recuperados: list[str]) -> bool:
    return any(r == o or r.startswith(o + ".") for o in ouros for r in recuperados)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", default="tfidf", choices=["tfidf", "e5"])
    p.add_argument("--modelo", default=E5_MODELO)
    p.add_argument("-k", type=int, default=3)
    a = p.parse_args()

    idx = Indice.carregar(a.backend, a.modelo)
    casos = [json.loads(l) for l in SUITE.open(encoding="utf-8") if l.strip()]
    destino = RAIZ / "resultados" / f"checagem_trechos_{idx.slug}_k{a.k}.csv"

    campos = ["caso", "classe", "consulta", "artigo_ouro"]
    for i in range(1, a.k + 1):
        campos += [f"top{i}_artigo", f"top{i}_score", f"top{i}_texto"]
    campos += ["ouro_no_topk"]

    acertos = com_ouro = 0
    with destino.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for c in casos:
            hits = idx.buscar(c["pergunta"], k=a.k)
            linha = {"caso": c["id"], "classe": c["classe"], "consulta": c["pergunta"],
                     "artigo_ouro": "|".join(c["artigo_ouro"])}
            for i, h in enumerate(hits, 1):
                linha[f"top{i}_artigo"] = h["artigo"]
                linha[f"top{i}_score"] = h["score"]
                linha[f"top{i}_texto"] = h["texto"]
            if c["artigo_ouro"]:
                ok = ouro_no_topk(c["artigo_ouro"], [h["artigo"] for h in hits])
                linha["ouro_no_topk"] = int(ok)
                com_ouro += 1
                acertos += ok
            else:
                linha["ouro_no_topk"] = ""
            w.writerow(linha)
            print(f"  {c['id']}  {'ok ' if linha['ouro_no_topk'] == 1 else '-- ' if linha['ouro_no_topk'] == 0 else '   '}"
                  f" ouro={linha['artigo_ouro']:<16} top={'|'.join(h['artigo'] for h in hits)}")

    print(f"\nartigo_ouro no top-{a.k}: {acertos}/{com_ouro} casos com ouro")
    print(destino.relative_to(RAIZ))


if __name__ == "__main__":
    main()
