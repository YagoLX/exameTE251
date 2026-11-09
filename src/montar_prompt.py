#!/usr/bin/env python3
"""
montar_prompt.py - monta o prompt do Ramo A para um caso da suite.

Este e o unico lugar onde o prompt de redacao existe. Ele vai literal para o
apendice do artigo: e a unica prova de que o Ramo A nao ve o Ramo B.

O prompt contem: os k trechos recuperados, o FEN, o tabuleiro em ASCII, o lance
descrito em palavras (so UCI + peca na origem) e a pergunta.
O prompt NAO contem, e nunca pode conter: a saida de legalidade(), o
veredito_ouro, o artigo_ouro, nem qualquer coisa vinda da suite alem da
pergunta e do FEN. Ha uma checagem no fim que falha se isso vazar.

Uso:
    python src/montar_prompt.py c12                      # imprime o prompt
    python src/montar_prompt.py c12 --salvar             # grava em resultados/prompts/
    python src/montar_prompt.py --todos --salvar         # todos os posicionais
    python src/montar_prompt.py c12 --backend e5
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chess  # noqa: E402  (so para desenhar o tabuleiro; nada de legalidade)
from buscar_artigo import Indice, E5_MODELO  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SUITE = RAIZ / "suite" / "suite_30.jsonl"
PROMPTS = RAIZ / "resultados" / "prompts"

GABARITO = """\
EXCERPTS FROM THE FIDE LAWS OF CHESS (retrieved for this question)
{trechos}

POSITION
FEN: {fen}
{tabuleiro}

MOVE IN QUESTION
{lance}

QUESTION
{pergunta}

INSTRUCTIONS
Answer only from the excerpts above, never from memory.
- Cite only an Article number that appears in the excerpts.
- If the excerpts do not settle the question, set "veredito" to exactly: nao consta no material
- Do not declare the game over, a penalty applied, or the position "in accordance with the rules".
- If there is a move, "veredito" is "legal", "ilegal" or "nao consta no material".
  If there is no move, "veredito" is a short answer (at most five words) or "nao consta no material".
Reply with one JSON object and nothing else:
{{"veredito": "...", "artigo": "<Article number or null>", "trecho_citado": "<sentence from the excerpt or null>", "justificativa": "<at most two sentences>"}}
"""

NOMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
         chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
PROMO = {"q": "queen", "r": "rook", "b": "bishop", "n": "knight"}


def tabuleiro_ascii(fen: str | None) -> str:
    """print(board) + quem joga. Nao consulta legalidade de nada."""
    if not fen:
        return "(no position given)"
    try:
        b = chess.Board(fen)
    except Exception:
        return "(FEN could not be read)"
    vez = "White" if b.turn == chess.WHITE else "Black"
    return f"{b}\n(uppercase = White, lowercase = Black; {vez} to move)"


def descrever_lance(fen: str | None, lance: str | None) -> str:
    """Descricao do lance SO a partir da string UCI e da peca na casa de origem.

    Proibido usar board.san(): ela so funciona para lance legal e escreve O-O-O,
    o que vazaria a legalidade para o Ramo A (invariante 2 do CLAUDE.md).
    """
    if not lance:
        return "(no specific move)"
    origem, destino, sufixo = lance[:2], lance[2:4], lance[4:]
    try:
        b = chess.Board(fen) if fen else None
        peca = b.piece_at(chess.parse_square(origem)) if b else None
    except Exception:
        peca = None
    if peca is None:
        texto = f"from {origem} to {destino} (no piece found on {origem})"
    else:
        cor = "White" if peca.color == chess.WHITE else "Black"
        texto = f"{cor} {NOMES[peca.piece_type]} from {origem} to {destino}"
    if sufixo:
        texto += f", becoming a {PROMO.get(sufixo.lower(), repr(sufixo))}"
    return f"{texto} (UCI: {lance})"


def carregar_suite() -> dict[str, dict]:
    if not SUITE.exists():
        sys.exit(f"ERRO: {SUITE} nao existe. Rode:  python3 suite/suite_30.py --emitir")
    return {json.loads(l)["id"]: json.loads(l) for l in SUITE.open(encoding="utf-8") if l.strip()}


# Os UNICOS campos do caso que podem entrar no prompt.
PERMITIDOS = ("pergunta", "fen", "lance")


def montar(caso: dict, idx: Indice, k: int) -> tuple[str, list[dict]]:
    """Monta o prompt a partir de PERMITIDOS e dos chunks, e de mais nada.

    A independencia dos ramos nao e garantida por busca de string: e garantida
    por construcao, porque esta funcao so le os campos de PERMITIDOS. O
    --autoteste prova isso mutando os campos de gabarito e exigindo que o
    prompt saia byte a byte identico.
    """
    caso = {campo: caso.get(campo) for campo in PERMITIDOS}
    # Pergunta do prompt = consulta da busca (decisao de 09/11).
    hits = idx.buscar(caso["pergunta"], k=k)
    trechos = "\n\n".join(
        f"[{i+1}] Article {h['artigo']} ({h['artigo_titulo']})\n{h['texto']}"
        for i, h in enumerate(hits))
    prompt = GABARITO.format(
        pergunta=caso["pergunta"],
        fen=caso["fen"] or "(none)",
        tabuleiro=tabuleiro_ascii(caso["fen"]),
        lance=descrever_lance(caso["fen"], caso["lance"]),
        trechos=trechos)

    return prompt, hits


def autoteste(idx: Indice, k: int) -> int:
    """Duas invariantes da arquitetura, verificaveis sem modelo nenhum."""
    falhas = 0

    # 1. Este modulo nao pode importar a autoridade factual.
    fonte = Path(__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    if "legalidade" in importados:
        print("  FALHA  montar_prompt importa legalidade: os ramos deixaram de ser independentes")
        falhas += 1
    else:
        print("  ok     montar_prompt nao importa legalidade")

    # 1b. Importa chess so para desenhar: nenhuma chamada que decida legalidade.
    proibidos = {"san", "is_legal", "legal_moves", "pseudo_legal_moves", "push", "is_check",
                 "is_checkmate", "is_stalemate", "is_insufficient_material", "can_claim_fifty_moves",
                 "is_attacked_by", "attackers", "is_valid", "status", "is_castling", "outcome"}
    usados = sorted({no.attr for no in ast.walk(arvore)
                     if isinstance(no, ast.Attribute) and no.attr in proibidos})
    if usados:
        print(f"  FALHA  montar_prompt usa API de legalidade do chess: {usados}")
        falhas += 1
    else:
        print("  ok     montar_prompt nao chama nenhuma API de legalidade do chess")

    # 2. Mutar o gabarito nao pode mudar um unico byte do prompt.
    iguais = 0
    casos = [c for c in carregar_suite().values() if c["fen"]]
    for caso in casos:
        limpo, _ = montar(caso, idx, k)
        sujo, _ = montar({**caso,
                          "veredito_ouro": "RESPOSTA_VAZADA",
                          "artigo_ouro": ["99.99.99"],
                          "parada_esperada": "VAZOU"}, idx, k)
        iguais += limpo == sujo
    if iguais == len(casos):
        print(f"  ok     prompt identico com gabarito mutado em {iguais}/{len(casos)} casos")
    else:
        print(f"  FALHA  prompt mudou em {len(casos) - iguais} casos ao mutar o gabarito")
        falhas += 1

    return falhas


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("caso", nargs="?", help="id do caso, ex. c12")
    p.add_argument("--todos", action="store_true", help="todos os casos com FEN")
    p.add_argument("--salvar", action="store_true")
    p.add_argument("--backend", default="tfidf", choices=["tfidf", "e5"])
    p.add_argument("--modelo", default=E5_MODELO)
    p.add_argument("-k", type=int, default=3)
    p.add_argument("--autoteste", action="store_true",
                   help="verifica as invariantes de independencia dos ramos")
    a = p.parse_args()

    suite = carregar_suite()
    idx = Indice.carregar(a.backend, a.modelo)

    if a.autoteste:
        print("invariantes da independencia dos ramos:")
        sys.exit(1 if autoteste(idx, a.k) else 0)

    if a.todos:
        alvos = [c for c in suite.values() if c["fen"]]
    elif a.caso:
        if a.caso not in suite:
            sys.exit(f"ERRO: caso '{a.caso}' nao existe. Ids: {', '.join(sorted(suite))}")
        alvos = [suite[a.caso]]
    else:
        p.error("informe um id de caso, ou use --todos")

    for caso in alvos:
        prompt, hits = montar(caso, idx, a.k)
        if a.salvar:
            PROMPTS.mkdir(parents=True, exist_ok=True)
            destino = PROMPTS / f"{caso['id']}_{a.backend}_k{a.k}.txt"
            destino.write_text(prompt, encoding="utf-8")
            arts = ", ".join(h["artigo"] for h in hits)
            print(f"{destino.relative_to(RAIZ)}   chunks: {arts}")
        else:
            print(prompt)


if __name__ == "__main__":
    main()
