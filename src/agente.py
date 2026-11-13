#!/usr/bin/env python3
"""
agente.py - o pipeline. Unico modulo que ve os dois ramos.

  pergunta -> classe (codigo: tem FEN?) -> Ramo A (busca + LLM)
           -> Ramo B (legalidade)       -> comparador -> trace JSON em traces/

O agente nao emite veredito a ninguem: a saida de cada execucao e o trace.
A revisao humana e feita depois, caso a caso (resultados/rotulos_humanos.json).

Passos por pergunta (limite 4, AGENTS.md): buscar, redigir (LLM), legalidade, comparar.
Ao modelo vai SO o prompt de montar_prompt: pergunta, posicao, lance e trechos do corpus publico.

Uso:
    python src/agente.py c12 --execucao 1
    python src/agente.py --todos --execucao 1     # as execucoes oficiais (em lote)
    python src/agente.py c12 --seco               # nao chama o modelo; testa o resto
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
# Segundo provedor, mesmo modelo, mesmo formato de API (OpenAI-compatível).
# Usado quando o Groq está fora do ar (404 em todos os endereços do Groq, observado em 10/11/2026).
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PROVEDORES = {
    "groq": {"url": GROQ_URL, "chave": "GROQ_API_KEY", "modelo_padrao": "openai/gpt-oss-120b"},
    "openrouter": {"url": OPENROUTER_URL, "chave": "OPENROUTER_API_KEY", "modelo_padrao": "openai/gpt-oss-120b"},
    # Modelo local via Ollama (sem chave, nada sai da maquina). Tempo limite maior: CPU.
    "ollama": {"url": "http://127.0.0.1:11434/v1/chat/completions", "chave": None,
               "modelo_padrao": "qwen3:8b", "timeout": 900},
}
PROVEDOR_PADRAO = "ollama"   # decisao de 11/11: modelo local (ver docs/estado_do_projeto.md)
# Escolhido em 09/11: gpt-oss-120b no Groq (llama-3.3-70b nao e mais servido; so ha
# Llama prompt-guard na lista de /models). O id SERVIDO
# vai para o trace (meta.modelo_servido); confira-o antes das 90 execucoes.
MODELO_PADRAO = "qwen3:8b"
K_PADRAO = 5            # 22/29 com ouro no top-5 (e5), contra 18/29 no top-3
BACKEND_PADRAO = "e5"


def ler_env() -> dict:
    """Le KEY=valor de .env na raiz (fora do git). Nunca grava a chave em trace."""
    arq = RAIZ / ".env"
    if not arq.exists():
        return {}
    return dict(l.split("=", 1) for l in arq.read_text().split() if "=" in l)


def chamar_llm(prompt: str, modelo: str, temperatura: float, provedor: str = PROVEDOR_PADRAO) -> tuple[str | None, dict]:
    cfg = PROVEDORES[provedor]
    nome_chave = cfg["chave"]
    cab = {"Content-Type": "application/json", "User-Agent": "te251-agente"}
    if nome_chave:
        chave = os.environ.get(nome_chave) or ler_env().get(nome_chave)
        if not chave:
            sys.exit(f"ERRO: defina {nome_chave} (ambiente ou arquivo .env na raiz)")
        cab["Authorization"] = f"Bearer {chave}"
    pedido = {
        "model": modelo, "temperature": temperatura,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    if provedor == "ollama":
        pedido["seed"] = 0                    # reprodutibilidade local
        pedido["reasoning_effort"] = "none"   # sem cadeia de raciocinio (tempo em CPU)
    req = urllib.request.Request(cfg["url"], data=json.dumps(pedido).encode(), headers=cab)
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=cfg.get("timeout", 60)) as r:
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


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rodar(caso: dict, idx: Indice, a) -> dict:
    """Roda os dois ramos e o comparador e devolve o trace. Nada e emitido.
    O campo `aprovacao` so guarda a decisao opcional de um revisor na interface
    (registrar_aprovacao); "pendente" quer dizer que nenhum revisor marcou o trace.
    `a` precisa de: modelo, temperatura, k, backend, seco, execucao."""
    passos = []
    classe = "posicional" if caso.get("fen") else "normativa"     # em codigo, nao por LLM

    prompt, hits = montar(caso, idx, a.k)                       # passo 1: buscar
    passos.append("buscar_artigo")
    if a.seco:
        bruto, meta = None, {"seco": True}
    else:
        bruto, meta = chamar_llm(prompt, a.modelo, a.temperatura, getattr(a, "provedor", PROVEDOR_PADRAO))  # passo 2: redigir
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
        "config": {"provedor": getattr(a, "provedor", PROVEDOR_PADRAO), "modelo": a.modelo, "temperatura": a.temperatura,
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
    """Grava no trace a decisao de um revisor (interface). Nunca apaga a anterior: empilha."""
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
    p.add_argument("--provedor", default=PROVEDOR_PADRAO, choices=list(PROVEDORES), help="onde roda o modelo (vai para o trace)")
    p.add_argument("--modelo", default=MODELO_PADRAO, help="id exato do modelo no provedor escolhido (vai para o trace)")
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
        (TRACES / nome).write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {t['caso']}  parada={t['parada']:<15} traces/{nome}")


if __name__ == "__main__":
    main()
