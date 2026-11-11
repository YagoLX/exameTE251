#!/usr/bin/env python3
"""
exportar_respostas.py - consolida as respostas das execucoes oficiais em um CSV.

Le traces/c*_r*.json (nao le traces/interface/ nem rotulos humanos) e grava
resultados/respostas_execucoes_oficiais.csv: so o que o Ramo A respondeu, o que o
Ramo B disse e a parada do comparador. Nao inclui o prompt nem rotulos humanos.
"""
import csv
import glob
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SUITE = {json.loads(l)["id"]: json.loads(l) for l in (RAIZ / "suite" / "suite_30.jsonl").open(encoding="utf-8")}
CAMPOS = ["caso", "execucao", "classe", "pergunta", "fen", "lance", "modelo", "veredito_a", "artigo_citado",
          "justificativa_a", "veredito_b", "parada", "parada_esperada", "veredito_ouro", "artigo_ouro",
          "artigos_recuperados", "ouro_no_topk"]


def linhas():
    for f in sorted(glob.glob(str(RAIZ / "traces" / "c*_r*.json"))):
        t = json.loads(Path(f).read_text(encoding="utf-8"))
        c = SUITE[t["caso"]]
        r = t["ramo_a"]["resposta"] or {}
        hits = [h["artigo"] for h in t["ramo_a"]["hits"]]
        ouro = c["artigo_ouro"] or []
        yield {
            "caso": t["caso"], "execucao": t["execucao"], "classe": t["classe"], "pergunta": t["pergunta"],
            "fen": t["fen"] or "", "lance": t["lance"] or "", "modelo": t["config"]["modelo"],
            "veredito_a": r.get("veredito", ""), "artigo_citado": r.get("artigo") or "",
            "justificativa_a": r.get("justificativa", ""),
            "veredito_b": (t["ramo_b"] or {}).get("veredito", ""), "parada": t["parada"],
            "parada_esperada": c["parada_esperada"], "veredito_ouro": c["veredito_ouro"] or "",
            "artigo_ouro": ";".join(ouro), "artigos_recuperados": ";".join(hits),
            "ouro_no_topk": ("" if not ouro else any(h == o or h.startswith(o + ".") for h in hits for o in ouro)),
        }


def main():
    destino = RAIZ / "resultados" / "respostas_execucoes_oficiais.csv"
    rows = list(linhas())
    with destino.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} execucoes -> {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
