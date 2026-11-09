#!/usr/bin/env python3
"""
legalidade.py - a autoridade factual (Ramo B do sistema).

Funcao pura sobre python-chess. Dada uma posicao em FEN e, opcionalmente, um
lance em UCI, devolve um veredito deterministico e os indicadores de estado.

NAO conhece o corpus. NAO importa buscar_artigo. NAO recebe nada do Ramo A.
Essa separacao e a razao de o no de discordancia poder medir alguma coisa:
se este arquivo soubesse o que o modelo respondeu, nao haveria o que comparar.

Uso:
    python src/legalidade.py "r3k2r/8/8/8/8/8/1r6/R3K2R w KQkq - 0 1" e1c1
    python src/legalidade.py "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"
    python src/legalidade.py --suite          # roda os casos posicionais da suite

Como biblioteca:
    from legalidade import legalidade
    legalidade("8/8/8/8/8/3k4/8/3K4 w - - 0 1", "d1d2")
    # {"veredito": "ilegal", "fonte": "python-chess 1.11.2", "flags": {...}, ...}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import chess

FONTE = f"python-chess {chess.__version__}"
PECAS_PROMOCAO = {"q", "r", "b", "n"}   # FIDE 3.7.3.3


def _flags(b: chess.Board) -> dict:
    return {
        "em_xeque": b.is_check(),
        "mate": b.is_checkmate(),
        "afogado": b.is_stalemate(),
        "material_insuficiente": b.is_insufficient_material(),
        "cinquenta_lances": b.can_claim_fifty_moves(),
        "n_lances_legais": b.legal_moves.count(),
        "vez_de": "brancas" if b.turn == chess.WHITE else "pretas",
    }


def legalidade(fen: str, lance: str | None = None) -> dict:
    """Veredito factual. Nunca levanta excecao: falha vira veredito 'erro'."""
    base = {"fen": fen, "lance": lance, "fonte": FONTE}

    try:
        b = chess.Board(fen)
    except Exception as e:
        return {**base, "veredito": "erro",
                "motivo": f"FEN imparsavel: {type(e).__name__}: {e}"}

    if not b.is_valid():
        return {**base, "veredito": "erro",
                "motivo": f"FEN sintaticamente ok mas posicao invalida: {b.status()!r}"}

    flags = _flags(b)

    # Sem lance: a pergunta e sobre o estado da posicao.
    if lance is None:
        if flags["mate"]:
            estado = "mate"
        elif flags["afogado"]:
            estado = "afogado"
        elif flags["material_insuficiente"]:
            estado = "posicao_morta"
        elif flags["cinquenta_lances"]:
            estado = "cinquenta_lances"
        else:
            estado = f"{flags['n_lances_legais']}_lances"
        return {**base, "veredito": estado, "flags": flags}

    # Com lance: a pergunta e sobre a legalidade dele.
    aviso = None
    if len(lance) == 5 and lance[4].lower() not in PECAS_PROMOCAO:
        aviso = (f"promocao para '{lance[4]}' nao e peca permitida; "
                 f"a FIDE admite apenas dama, torre, bispo ou cavalo")
    try:
        m = chess.Move.from_uci(lance)
    except Exception as e:
        return {**base, "veredito": "erro", "flags": flags,
                "motivo": f"lance imparsavel: {type(e).__name__}: {e}"}

    if not b.is_legal(m):
        saida = {**base, "veredito": "ilegal", "flags": flags}
        if aviso:
            saida["aviso"] = aviso
        return saida

    san = b.san(m)
    b.push(m)
    return {**base, "veredito": "legal", "san": san, "flags": flags,
            "depois": {"em_xeque": b.is_check(), "mate": b.is_checkmate(),
                       "afogado": b.is_stalemate()}}


def rodar_suite() -> int:
    caminho = Path(__file__).resolve().parents[1] / "suite" / "suite_30.jsonl"
    if not caminho.exists():
        sys.exit(f"ERRO: {caminho} nao existe. Rode antes:\n"
                 f"  python3 suite/suite_30.py --emitir")
    casos = [json.loads(l) for l in caminho.open(encoding="utf-8") if l.strip()]
    posicionais = [c for c in casos if c["fen"]]
    falhas = 0
    print(f"{FONTE} | {len(posicionais)} casos posicionais de {len(casos)}\n")
    for c in posicionais:
        r = legalidade(c["fen"], c["lance"])
        ok = r["veredito"] == c["veredito_ouro"]
        falhas += not ok
        extra = f"  <- {r['aviso']}" if r.get("aviso") else ""
        print(f"  {'ok ' if ok else 'FALHA'} {c['id']}  "
              f"ouro={c['veredito_ouro']:<18} obtido={r['veredito']:<18} "
              f"{c['pergunta'][:40]}{extra}")
    print(f"\n{len(posicionais) - falhas}/{len(posicionais)} conferem")
    return falhas


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fen", nargs="?")
    p.add_argument("lance", nargs="?")
    p.add_argument("--suite", action="store_true", help="rodar os casos da suite")
    a = p.parse_args()

    if a.suite:
        sys.exit(1 if rodar_suite() else 0)
    if not a.fen:
        p.error("informe um FEN, ou use --suite")
    print(json.dumps(legalidade(a.fen, a.lance), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
