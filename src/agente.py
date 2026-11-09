#!/usr/bin/env python3
"""
agente.py - o pipeline. Unico modulo que ve os dois ramos.

  pergunta -> classe (codigo: tem FEN?) -> Ramo A (busca + LLM no Groq)
           -> Ramo B (legalidade)       -> comparador -> trace JSON em traces/
           -> aprovacao humana (input s/n, gravada no trace)

Passos por pergunta (limite 4, AGENTS.md): buscar, redigir (LLM), legalidade, comparar.
Ao Groq vao SO o prompt de montar_prompt: pergunta, FEN e trechos do corpus publico.

Uso:
    export GROQ_API_KEY=...
    python src/agente.py c12 --execucao 1
    python src/agente.py --todos --execucao 1     # pede aprovacao a cada caso
    python src/agente.py c12 --seco               # nao chama a API; testa o resto
    (interface grafica: python src/interface.py)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buscar_artigo import Indice, E5_MODELO  # noqa: E402
from comparador import comparar  # noqa: E402
from legalidade import legalidade  # noqa: E402
from montar_prompt import montar, carregar_suite  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
TRACES = RAIZ / "traces"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Escolhido em 09/11: gpt-oss-120b no Groq (llama-3.3-70b nao e mais servido; so ha
# Llama prompt-guard na lista de /models). O id SERVIDO
# vai para o trace (meta.modelo_servido); confira-o antes das 90 execucoes.
MODELO_PADRAO = "openai/gpt-oss-120b"
K_PADRAO = 5            # 22/29 com ouro no top-5 (e5), contra 18/29 no top-3
BACKEND_PADRAO = "e5"


def ler_env() -> dict:
    """Le KEY=valor de .env na raiz (fora do git). Nunca grava a chave em trace."""
    arq = RAIZ / ".env"
    if not arq.exists():
        return {}
    return dict(l.split("=", 1) for l in arq.read_text().split() if "=" in l)


def chamar_groq(prompt: str, modelo: str, temperatura: float) -> tuple[str | None, dict]:
    chave = os.environ.get("GROQ_API_KEY") or ler_env().get("GROQ_API_KEY")
    if not chave:
        sys.exit("ERRO: defina GROQ_API_KEY (ambiente ou arquivo .env na raiz)")
    corpo = json.dumps({
        "model": modelo, "temperature": temperatura,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(GROQ_URL, data=corpo, headers={
        "Authorization": f"Bearer {chave}", "Content-Type": "application/json",
        "User-Agent": "te251-agente"})
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            return d["choices"][0]["message"]["content"], {
                "modelo_servido": d.get("model"), "uso": d.get("usage"),
                "system_fingerprint": d.get("system_fingerprint"), "tentativas": tentativa + 1}
        except urllib.error.HTTPError as e:
            if e.code == 429 and tentativa < 3:      # rate limit do free tier
                time.sleep(float(e.headers.get("retry-after", 10)))
                continue
            return None, {"erro_http": e.code, "corpo": e.read().decode(errors="replace")[:500]}
        except Exception as e:
            return None, {"erro": f"{type(e).__name__}: {e}"}
    return None, {"erro": "rate limit persistente"}


def parsear(bruto: str | None) -> dict | None:
    if not bruto:
        return None
    m = re.search(r"\{.*\}", bruto, re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) else None


def aprovar(trace: dict) -> dict:
    """Unica acao com efeito externo: emitir o veredito. Exige um humano."""
    if not sys.stdin.isatty():
        return {"decisao": "pendente", "motivo": "sem terminal interativo", "em": agora()}
    p, a = trace["parada"], trace["ramo_a"]["resposta"] or {}
    print(f"\n[{trace['caso']}] parada={p}  A={a.get('veredito')!r} art={a.get('artigo')}  "
          f"B={(trace['ramo_b'] or {}).get('veredito')!r}")
    if p == "discordam":
        print("  Ramos discordam: nenhuma resposta e redigida; vai para revisao humana.")
    r = input("  Aprovar emissao? [s/n] ").strip().lower()
    return {"decisao": "aprovado" if r == "s" else "rejeitado", "entrada": r, "via": "terminal", "em": agora()}


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rodar(caso: dict, idx: Indice, a) -> dict:
    """Roda os dois ramos e o comparador. A aprovacao fica 'pendente': quem a
    decide e um humano, pelo terminal (aprovar) ou pela interface (registrar_aprovacao).
    `a` precisa de: modelo, temperatura, k, backend, seco, execucao."""
    passos = []
    classe = "posicional" if caso.get("fen") else "normativa"     # em codigo, nao por LLM

    prompt, hits = montar(caso, idx, a.k)                       # passo 1: buscar
    passos.append("buscar_artigo")
    if a.seco:
        bruto, meta = None, {"seco": True}
    else:
        bruto, meta = chamar_groq(prompt, a.modelo, a.temperatura)  # passo 2: redigir
        passos.append("llm")
    resposta = parsear(bruto)

    if classe == "posicional":
        b = legalidade(caso["fen"], caso.get("lance"))         # passo 3
        passos.append("legalidade")
        comp = comparar(resposta, b)                           # passo 4
        passos.append("comparador")
    else:
        b = None
        comp = ({"parada": "erro", "motivo": "Ramo A sem JSON valido"} if resposta is None else
                {"parada": "recusa" if str(resposta.get("veredito", "")).strip().lower()
                 == "nao consta no material" else "sem_verificacao",
                 "motivo": "sem FEN: nada a comparar"})
    assert len(passos) <= 4

    trace = {
        "caso": caso["id"], "execucao": a.execucao, "inicio": agora(), "classe": classe,
        "config": {"provedor": "groq", "modelo": a.modelo, "temperatura": a.temperatura,
                   "k": a.k, "backend": a.backend, "indice": idx.slug},
        "pergunta": caso["pergunta"], "fen": caso.get("fen"), "lance": caso.get("lance"),
        "ramo_a": {"hits": hits, "prompt": prompt,
                   "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                   "bruto": bruto, "resposta": resposta, "meta": meta},
        "ramo_b": b, "parada": comp["parada"], "comparador": comp, "passos": passos,
    }
    trace["aprovacao"] = {"decisao": "pendente", "em": agora()}
    return trace


def registrar_aprovacao(caminho: Path, decisao: str, via: str) -> dict:
    """Grava a decisao humana no trace. Nunca apaga a decisao anterior: empilha."""
    t = json.loads(caminho.read_text(encoding="utf-8"))
    anterior = t.get("aprovacao")
    t["aprovacao"] = {"decisao": decisao, "via": via, "em": agora()}
    if anterior and anterior.get("decisao") != "pendente":
        t.setdefault("aprovacoes_anteriores", []).append(anterior)
    caminho.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    return t


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("caso", nargs="?")
    p.add_argument("--todos", action="store_true")
    p.add_argument("--modelo", default=MODELO_PADRAO, help="id exato do modelo no Groq (vai para o trace)")
    p.add_argument("--temperatura", type=float, default=0.0)
    p.add_argument("--execucao", type=int, default=1)
    p.add_argument("--backend", default=BACKEND_PADRAO, choices=["tfidf", "e5"])
    p.add_argument("--modelo-e5", default=E5_MODELO)
    p.add_argument("-k", type=int, default=K_PADRAO)
    p.add_argument("--seco", action="store_true", help="nao chama a API")
    a = p.parse_args()

    suite = carregar_suite()
    alvos = list(suite.values()) if a.todos else [suite[a.caso]] if a.caso in suite else None
    if not alvos:
        p.error("informe um id de caso valido, ou --todos")
    idx = Indice.carregar(a.backend, a.modelo_e5)

    TRACES.mkdir(exist_ok=True)
    for caso in alvos:
        nome = f"{caso['id']}_r{a.execucao}{'_seco' if a.seco else ''}.json"
        if (TRACES / nome).exists() and not a.seco:
            print(f"  {caso['id']}  pulado: traces/{nome} ja existe (trace nao se sobrescreve)")
            continue
        t = rodar(caso, idx, a)
        t["aprovacao"] = aprovar(t)
        (TRACES / nome).write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {t['caso']}  parada={t['parada']:<15} aprovacao={t['aprovacao']['decisao']:<10} traces/{nome}")


if __name__ == "__main__":
    main()
