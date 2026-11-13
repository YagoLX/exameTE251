#!/usr/bin/env python3
"""
grader.py - avalia as execucoes oficiais a partir dos traces. Codigo, sem IA.

Le traces/c*_r*.json (as 105 execucoes oficiais; NAO le traces/interface/),
suite/suite_30.jsonl (gabarito humano) e resultados/rotulos_humanos.json, e grava:

  resultados/grader_execucoes.csv   uma linha por execucao, com cada criterio
  resultados/grader_resumo.json     todas as contagens (fonte dos numeros do artigo)
  resultados/grader_resumo.md       o mesmo resumo, legivel

Criterios binarios por execucao (regras declaradas aqui, aplicadas igual a todas):

  citacao_identificavel  O Ramo A citou um artigo e o numero e EXATAMENTE o de um dos
                         trechos recuperados nesta execucao. Citar so o item pai
                         ("3" quando o trecho e "3.8.2.2") NAO conta.
                         Nao se aplica quando o Ramo A recusou ou nao devolveu JSON.
  trecho_ancorado        O "trecho_citado" aparece literalmente (comparando so letras e
                         digitos, sem caixa) no texto de um dos trechos recuperados.
                         E um proxy automatico de "resposta sustentada pelo trecho": prova
                         que a citacao veio do material, nao que a justificativa esta certa.
                         Nao se aplica quando o Ramo A recusou ou nao devolveu JSON.
  recusa_correta         Recusou ("nao consta no material") se e somente se a suite
                         espera recusa (parada_esperada == "recusa").

A revisao humana nao e criterio automatico: ela foi feita depois das execucoes,
caso a caso, e o grader so resume os rotulos de resultados/rotulos_humanos.json.

Alem disso, so para os casos posicionais:
  veredito_a_correto     veredito do Ramo A == veredito_ouro (normalizado como no comparador)
  veredito_b_correto     veredito do Ramo B == veredito_ouro

pass^3 e MEDIDO: um caso passa num criterio quando o criterio passa nas 3 repeticoes.
Nao e calculado como p^3. Casos em que o criterio nao se aplica em alguma repeticao
ficam fora do denominador.

Uso:  python3 src/grader.py
"""
from __future__ import annotations

import csv
import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comparador import RECUSA, comparar, _norm  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
RES = RAIZ / "resultados"
SUITE = {json.loads(l)["id"]: json.loads(l)
         for l in (RAIZ / "suite" / "suite_30.jsonl").open(encoding="utf-8") if l.strip()}
CRITERIOS = ["citacao_identificavel", "trecho_ancorado", "recusa_correta"]


def alnum(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def numero_artigo(s) -> str | None:
    m = re.search(r"\d+(?:\.\d+)*", str(s or ""))
    return m.group(0) if m else None


def ouro_no_topk(hits: list[str], ouro: list[str]) -> bool:
    return any(h == o or h.startswith(o + ".") for h in hits for o in ouro)


def avaliar(t: dict) -> dict:
    caso = SUITE[t["caso"]]
    resp = t["ramo_a"]["resposta"]
    hits = t["ramo_a"]["hits"]
    arts = [h["artigo"] for h in hits]
    recusou = bool(resp) and _norm(resp.get("veredito", "")) == RECUSA
    respondeu = bool(resp) and not recusou
    ouro = caso.get("artigo_ouro") or []

    r = {
        "caso": t["caso"], "execucao": t["execucao"], "classe": t["classe"],
        "parada": t["parada"], "parada_esperada": caso["parada_esperada"],
        "veredito_a": (resp or {}).get("veredito", ""), "artigo_citado": (resp or {}).get("artigo") or "",
        "veredito_b": (t["ramo_b"] or {}).get("veredito", ""), "veredito_ouro": caso.get("veredito_ouro") or "",
        "artigo_ouro": ";".join(ouro), "artigos_recuperados": ";".join(arts),
        "ouro_no_topk": ouro_no_topk(arts, ouro) if ouro else "",
    }
    if respondeu:
        r["citacao_identificavel"] = numero_artigo(resp.get("artigo")) in arts
        alvo = alnum(resp.get("trecho_citado"))
        r["trecho_ancorado"] = bool(alvo) and any(alvo in alnum(h["texto"]) for h in hits)
    else:
        r["citacao_identificavel"] = r["trecho_ancorado"] = ""      # nao se aplica
    r["recusa_correta"] = recusou == (caso["parada_esperada"] == "recusa")

    if t["classe"] == "posicional":
        ouro_v = caso["veredito_ouro"]
        # Mesma regra de casamento do comparador, aplicada contra o gabarito em vez do Ramo B.
        a_ok = (respondeu and comparar(resp, {"lance": t["lance"], "veredito": ouro_v})["parada"] == "concordam")
        r["veredito_a_correto"] = a_ok
        r["veredito_b_correto"] = r["veredito_b"] == ouro_v
    else:
        r["veredito_a_correto"] = r["veredito_b_correto"] = ""
    return r


def main() -> None:
    arquivos = sorted(glob.glob(str(RAIZ / "traces" / "c*_r*.json")))
    traces = [json.loads(Path(f).read_text(encoding="utf-8")) for f in arquivos]
    linhas = [avaliar(t) for t in traces]
    por_caso = defaultdict(list)
    for l in linhas:
        por_caso[l["caso"]].append(l)

    # ---- configuracao: tudo fixo? ----
    configs = Counter(json.dumps(t["config"], sort_keys=True) for t in traces)
    servidos = Counter(str(t["ramo_a"]["meta"].get("modelo_servido")) for t in traces)
    prompts_por_caso = {c: len({t["ramo_a"]["prompt_sha256"] for t in traces if t["caso"] == c}) for c in por_caso}

    # ---- criterios: taxa por execucao e pass^3 por caso ----
    crit = {}
    for c in CRITERIOS + ["veredito_a_correto", "veredito_b_correto"]:
        apl = [l for l in linhas if l[c] != ""]
        casos_apl = [k for k, ls in por_caso.items() if len(ls) == 3 and all(x[c] != "" for x in ls)]
        crit[c] = {
            "execucoes_passam": sum(bool(l[c]) for l in apl), "execucoes_aplicaveis": len(apl),
            "casos_pass3": sum(all(x[c] for x in por_caso[k]) for k in casos_apl),
            "casos_aplicaveis": len(casos_apl),
            "casos_falham_alguma": sorted(k for k in casos_apl if not all(x[c] for x in por_caso[k])),
        }

    # ---- paradas ----
    paradas = Counter(l["parada"] for l in linhas)
    paradas_classe = Counter(f'{l["classe"]}:{l["parada"]}' for l in linhas)
    parada_bate = Counter()
    for l in linhas:
        esp = l["parada_esperada"]
        esp = "discordam" if esp == "discordancia_esperada" else esp
        parada_bate["igual" if l["parada"] == esp else "diferente"] += 1
    casos_parada_diferente = sorted({l["caso"] for l in linhas
                                     if l["parada"] != ("discordam" if l["parada_esperada"] == "discordancia_esperada"
                                                        else l["parada_esperada"])})

    # ---- discordancia entre os ramos (posicionais) ----
    pos = [l for l in linhas if l["classe"] == "posicional"]
    disc = [l for l in pos if l["parada"] == "discordam"]
    quem = Counter("so_A_errou" if (not l["veredito_a_correto"] and l["veredito_b_correto"]) else
                   "so_B_errou" if (l["veredito_a_correto"] and not l["veredito_b_correto"]) else
                   "ambos_erraram" for l in disc)
    conc = [l for l in pos if l["parada"] == "concordam"]
    conc_sem_ouro = sorted({l["caso"] for l in conc if l["ouro_no_topk"] is False})
    conc_citacao_errada = sorted({l["caso"] for l in conc if not l["citacao_identificavel"]})

    # ---- estabilidade entre repeticoes ----
    variaram = {}
    for k, ls in por_caso.items():
        vs = {(l["veredito_a"], l["artigo_citado"]) for l in ls}
        if len(vs) > 1:
            variaram[k] = sorted(f"{v}|{a}" for v, a in vs)

    # ---- busca (das proprias execucoes) ----
    com_ouro = [k for k in por_caso if SUITE[k].get("artigo_ouro")]
    busca_top5 = sum(por_caso[k][0]["ouro_no_topk"] is True for k in com_ouro)

    # ---- revisao humana (posterior, por rotulos) ----
    rot_path = RES / "rotulos_humanos.json"
    rot = json.loads(rot_path.read_text(encoding="utf-8")) if rot_path.exists() else {"casos": {}, "traces": {}}
    rot_casos = rot.get("casos", {})
    rotulos = {
        "casos_rotulados": len(rot_casos),
        "trechos": dict(Counter(v["trechos"] for v in rot_casos.values() if v.get("trechos"))),
        "revisao_do_caso": dict(Counter(v["revisao"] for v in rot_casos.values() if v.get("revisao"))),
        "achados_da_revisao": {k: v["revisao"] for k, v in sorted(rot_casos.items())
                               if v.get("revisao") in ("ajustar", "remover")},
        "traces_com_rotulo_de_resposta": len(rot.get("traces", {})),
    }

    resumo = {
        "execucoes": len(linhas), "casos": len(por_caso),
        "config": {"distintas": len(configs), "valores": [json.loads(c) for c in configs],
                   "modelo_servido": dict(servidos),
                   "casos_com_prompt_identico_nas_3": sum(n == 1 for n in prompts_por_caso.values())},
        "criterios": crit,
        "paradas": dict(paradas), "paradas_por_classe": dict(paradas_classe),
        "parada_vs_esperada": dict(parada_bate), "casos_parada_diferente_da_esperada": casos_parada_diferente,
        "posicionais": {
            "execucoes": len(pos), "casos": len({l["caso"] for l in pos}),
            "discordam_execucoes": len(disc), "discordam_casos": sorted({l["caso"] for l in disc}),
            "quem_errou_nas_discordancias": dict(quem),
            "concordam_execucoes": len(conc), "concordam_casos": sorted({l["caso"] for l in conc}),
            "concordam_sem_artigo_ouro_nos_trechos": conc_sem_ouro,
            "concordam_com_citacao_nao_identificavel": conc_citacao_errada,
        },
        "variacao_entre_repeticoes": variaram,
        "busca_ouro_no_top5": {"casos": busca_top5, "de": len(com_ouro)},
        "revisao_humana": rotulos,
    }

    RES.mkdir(exist_ok=True)
    campos = list(linhas[0].keys())
    with (RES / "grader_execucoes.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    (RES / "grader_resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    (RES / "grader_resumo.md").write_text(markdown(resumo), encoding="utf-8")
    print(markdown(resumo))


def markdown(r: dict) -> str:
    c, p, h = r["criterios"], r["posicionais"], r["revisao_humana"]
    L = [f"# Resumo do grader ({r['execucoes']} execucoes oficiais, {r['casos']} casos)", "",
         "Gerado por `python3 src/grader.py` a partir de `traces/c*_r*.json`. Regras dos criterios no docstring do script.", "",
         f"- Configuracoes distintas: {r['config']['distintas']} ({r['config']['valores'][0]['modelo']}, "
         f"temperatura {r['config']['valores'][0]['temperatura']}, k={r['config']['valores'][0]['k']}, "
         f"{r['config']['valores'][0]['backend']}); modelo servido: {r['config']['modelo_servido']}",
         f"- Casos com o mesmo prompt (sha256) nas 3 repeticoes: {r['config']['casos_com_prompt_identico_nas_3']}/{r['casos']}", "",
         "## Criterios", "", "| criterio | execucoes que passam | pass^3 (casos) | casos que falham em alguma |",
         "|---|---|---|---|"]
    for k, v in c.items():
        L.append(f"| {k} | {v['execucoes_passam']}/{v['execucoes_aplicaveis']} | {v['casos_pass3']}/{v['casos_aplicaveis']} "
                 f"| {', '.join(v['casos_falham_alguma']) or '-'} |")
    L += ["", "## Paradas", "", f"- Todas: {r['paradas']}", f"- Por classe: {r['paradas_por_classe']}",
          f"- Parada igual a esperada: {r['parada_vs_esperada']}; casos diferentes: {', '.join(r['casos_parada_diferente_da_esperada'])}",
          "", "## Discordancia entre os ramos (posicionais)", "",
          f"- {p['execucoes']} execucoes em {p['casos']} casos",
          f"- Discordam: {p['discordam_execucoes']} execucoes, casos {', '.join(p['discordam_casos'])}",
          f"- Quem errou nas discordancias: {p['quem_errou_nas_discordancias']}",
          f"- Concordam: {p['concordam_execucoes']} execucoes, casos {', '.join(p['concordam_casos'])}",
          f"- Concordam sem o artigo do gabarito nos trechos: {', '.join(p['concordam_sem_artigo_ouro_nos_trechos']) or '-'}",
          f"- Concordam com citacao nao identificavel: {', '.join(p['concordam_com_citacao_nao_identificavel']) or '-'}",
          "", "## Estabilidade", "",
          f"- Casos que variaram entre as 3 repeticoes: {len(r['variacao_entre_repeticoes'])} "
          f"({'; '.join(f'{k}: {v}' for k, v in r['variacao_entre_repeticoes'].items()) or '-'})",
          "", "## Busca", "", f"- Artigo do gabarito entre os 5 trechos: {r['busca_ouro_no_top5']['casos']}/{r['busca_ouro_no_top5']['de']} casos",
          "", "## Revisao humana (posterior, em resultados/rotulos_humanos.json)", "",
          f"- Casos rotulados: {h['casos_rotulados']}",
          f"- Trechos recuperados: {h['trechos']}",
          f"- Revisao do caso: {h['revisao_do_caso']}",
          f"- Achados da revisao, declarados como limitacao (a suite fica congelada depois das execucoes): "
          f"{', '.join(f'{k} {v}' for k, v in h['achados_da_revisao'].items()) or '-'}",
          f"- Traces com rotulo de resposta: {h['traces_com_rotulo_de_resposta']}", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
