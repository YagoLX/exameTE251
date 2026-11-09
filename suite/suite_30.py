#!/usr/bin/env python3
"""
suite_30.py - a fonte da suite de avaliacao, e o script que a verifica.

O veredito de cada caso posicional foi escrito A MAO (coluna veredito_ouro) e
depois CONFERIDO contra python-chess. Os dois tem de concordar. Se divergirem, o
script falha e aponta a linha: ou o gabarito esta errado, ou o FEN nao e o que
pensamos. Em nenhum caso o gabarito e "o que a biblioteca disser".

O artigo_ouro e inteiramente humano: foi lido do corpus, nao inferido.

Uso:
    python suite/suite_30.py --verificar          # confere os 24 posicionais
    python suite/suite_30.py --emitir             # escreve suite/suite_30.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import chess

AQUI = Path(__file__).resolve().parent

# id, classe, fen, lance, pergunta_pt, artigo_ouro, veredito_ouro, parada_esperada
CASOS = [
    # --- en passant ---
    ("c01", "posicional", "rnbqkbnr/ppp2ppp/4p3/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3", "e5d6",
     "As brancas podem capturar en passant?", ["3.7.3.1", "3.7.3.2"], "legal", "concordam"),
    ("c02", "posicional", "rnbqkbnr/ppp2ppp/4p3/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3", "e5d6",
     "Sem direito de en passant registrado, pode?", ["3.7.3.2"], "ilegal", "concordam"),
    ("c03", "posicional", "8/8/8/8/k1pP3R/8/8/4K3 b - d3 0 1", "c4d3",
     "A captura en passant esta disponivel aqui?", ["3.9.2", "3.7.3.2"], "ilegal", "concordam"),
    ("c04", "posicional", "rnbqkbnr/p1pppppp/8/PpP5/8/8/1P1PPPPP/RNBQKBNR w KQkq b6 0 3", "a5b6",
     "O peao de a5 pode capturar en passant?", ["3.7.3.1", "3.7.3.2"], "legal", "concordam"),
    # --- promocao ---
    ("c05", "posicional", "8/P6k/8/8/8/8/8/K7 w - - 0 1", "a7a8q",
     "O peao pode promover a dama?", ["3.7.3.3"], "legal", "concordam"),
    ("c06", "posicional", "1r5k/P7/8/8/8/8/8/K7 w - - 0 1", "a7b8q",
     "Pode promover capturando?", ["3.7.3.3"], "legal", "concordam"),
    ("c07", "posicional", "8/P6k/8/8/8/8/8/K7 w - - 0 1", "a7a8k",
     "Pode promover a rei?", ["3.7.3.3"], "ilegal", "concordam"),
    ("c08", "posicional", "8/4k1P1/8/8/8/8/8/K7 w - - 0 1", "g7g8n",
     "Promover a cavalo da xeque?", ["3.7.3.3", "3.9.1"], "legal", "concordam"),
    # --- roque ---
    ("c09", "posicional", "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1",
     "O roque curto e permitido?", ["3.8.2"], "legal", "concordam"),
    ("c10", "posicional", "r3k2r/8/8/8/8/8/4r3/R3K2R w KQkq - 0 1", "e1g1",
     "Pode rocar estando em xeque?", ["3.8.2.2"], "ilegal", "concordam"),
    ("c11", "posicional", "r3k2r/8/8/8/8/8/5r2/R3K2R w KQkq - 0 1", "e1g1",
     "Pode rocar se f1 esta atacada?", ["3.8.2.2"], "ilegal", "concordam"),
    ("c12", "posicional", "r3k2r/8/8/8/8/8/1r6/R3K2R w KQkq - 0 1", "e1c1",
     "Pode rocar longo se b1 esta atacada?", ["3.8.2.2"], "legal", "discordancia_esperada"),
    ("c13", "posicional", "r3k2r/8/8/8/8/8/8/R3K2R w kq - 0 1", "e1g1",
     "O rei ja mexeu. Pode rocar?", ["3.8.2.1"], "ilegal", "concordam"),
    ("c14", "posicional", "r3k2r/8/8/8/8/8/6r1/R3K2R w KQkq - 0 1", "e1g1",
     "Pode rocar se g1 esta atacada?", ["3.8.2.2"], "ilegal", "concordam"),
    # --- xeque e cravada ---
    ("c15", "posicional", "4r2k/8/8/8/8/8/4N3/4K3 w - - 0 1", "e2c3",
     "O cavalo pode sair de e2?", ["3.9.2"], "ilegal", "concordam"),
    ("c16", "posicional", "4k3/8/8/8/8/5r2/8/4K3 w - - 0 1", "e1f1",
     "O rei pode ir para f1?", ["3.9.2"], "ilegal", "concordam"),
    ("c17", "posicional", "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1", "e1e2",
     "O rei pode capturar a torre que da xeque?", ["3.9.1", "3.8.1"], "legal", "concordam"),
    ("c18", "posicional", "8/8/8/8/8/3k4/8/3K4 w - - 0 1", "d1d2",
     "O rei pode avancar para d2?", ["3.9.2"], "ilegal", "concordam"),
    # --- fim de partida ---
    ("c19", "posicional", "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "a1a8",
     "Ra8 da mate?", ["1.4.1", "5.1.1"], "legal", "concordam"),
    ("c20", "posicional", "6k1/5p1p/8/8/8/8/8/R5K1 w - - 0 1", "a1a8",
     "Ra8 da mate?", ["5.1.1", "3.9.1"], "legal", "concordam"),
    ("c21", "posicional", "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", None,
     "As pretas tem lance legal?", ["5.2.1"], "afogado", "concordam"),
    ("c22", "posicional", "4k3/8/8/8/8/8/8/4KN2 w - - 0 1", None,
     "Algum dos lados ainda pode dar mate?", ["5.2.2"], "posicao_morta", "concordam"),
    ("c23", "posicional", "8/8/4k3/8/8/4K3/8/7R w - - 100 80", None,
     "Cabe reclamar empate pelos 50 lances?", ["9.3"], "cinquenta_lances", "concordam"),
    ("c24", "posicional", "r3k2r/8/8/8/8/8/1r6/R3K2R w KQkq - 0 1", None,
     "Quantos lances legais as brancas tem?", [], "23_lances", "recusa"),
    # --- so corpus: a ferramenta nao alcanca ---
    ("c25", "hibrida", None, None,
     "Um lance ilegal foi completado. O que acontece?", ["7.5.1"], None, "concordam"),
    ("c26", "normativa", None, None,
     "E se for o segundo lance ilegal do mesmo jogador?", ["7.5.5"], None, "sem_verificacao"),
    ("c27", "normativa", None, None,
     "As pecas foram deslocadas sem intencao. Como se repara?", ["7.4"], None, "sem_verificacao"),
    ("c28", "normativa", None, None,
     "Houve tripla repeticao nesta partida?", ["9.2"], None, "ramo_de_erro"),
    ("c29", "normativa", None, None,
     "A bandeira do relogio caiu. Quem perde?", ["6.9"], None, "sem_verificacao"),
    ("c30", "normativa", None, None,
     "O celular de um jogador tocou. Qual a regra?", ["11.3.2"], None, "sem_verificacao"),
    # --- fora de escopo: RASCUNHO de 09/11, aguarda revisao humana antes de congelar ---
    # Temas com 0 ocorrencias em corpus/chunks.jsonl (que so tem os Artigos 0-12).
    # c31: Chess960 esta nas Guidelines da FIDE, mas NAO no corpus indexado:
    #      testa se o modelo responde de memoria.
    ("c31", "normativa", None, None,
     "Como se faz o roque no Chess960?", [], None, "recusa"),
    ("c32", "normativa", None, None,
     "Quantos pontos de rating perco se perder por W.O.?", [], None, "recusa"),
    ("c33", "normativa", None, None,
     "No bughouse, posso colocar um peao na primeira fileira?", [], None, "recusa"),
    ("c34", "normativa", None, None,
     "Qual sistema de desempate se usa num torneio suico?", [], None, "recusa"),
    ("c35", "normativa", None, None,
     "No Armageddon, quem vence se a partida empatar?", [], None, "recusa"),
]


# Perguntas em ingles (decisao de 09/11: a busca TF-IDF zera em portugues).
# Escritas como um jogador perguntaria, sem copiar o vocabulario da FIDE, e
# FIXADAS antes de rodar a busca. Nao reescrever depois de ver um caso falhar.
# A pergunta em ingles e ao mesmo tempo a do prompt e a consulta da busca.
PERGUNTAS_EN = {
    "c01": "Can White take the d5 pawn en passant here?",
    "c02": "Black's pawn is right next to mine on d5. Can I take it en passant?",
    "c03": "Can Black take the d4 pawn en passant?",
    "c04": "Can my pawn on a5 take the b5 pawn en passant?",
    "c05": "Can I push my pawn to a8 and make a queen?",
    "c06": "Can my pawn take the rook on b8 and become a queen?",
    "c07": "Can my pawn turn into a second king when it reaches the last rank?",
    "c08": "Can I promote to a knight on g8 to give check?",
    "c09": "Am I allowed to castle kingside here?",
    "c10": "I'm in check from the rook. Can I castle to get out of it?",
    "c11": "Black's rook is hitting f1. Can I still castle short?",
    "c12": "Can I castle queenside even though b1 is under attack?",
    "c13": "My king moved earlier and went back to e1. Can I castle now?",
    "c14": "Black's rook is controlling g1. Can I castle short?",
    "c15": "Can I move my knight off e2?",
    "c16": "Can my king step to f1?",
    "c17": "Can my king just take the rook that is checking it?",
    "c18": "Can my king move up to d2, right next to the other king?",
    "c19": "Is Ra8 checkmate?",
    "c20": "Is Ra8 checkmate here?",
    "c21": "It's Black to move. Does Black have any legal move?",
    "c22": "Can either side still checkmate with just a knight?",
    "c23": "Nobody has moved a pawn or captured for 50 moves. Can I claim a draw?",
    "c24": "How many legal moves does White have here?",
    "c25": "My opponent made an illegal move and pressed the clock. What happens now?",
    "c26": "What if the same player makes a second illegal move in the game?",
    "c27": "I knocked some pieces over by accident. How do we fix the board?",
    "c28": "Was there a threefold repetition in this game?",
    "c29": "My opponent's flag fell. Do they lose?",
    "c30": "A player's phone rang during the game. What's the rule?",
    "c31": "How does castling work in Chess960?",
    "c32": "How many rating points do I lose if I forfeit a game?",
    "c33": "In bughouse, can I drop a pawn on the first rank?",
    "c34": "Which tiebreak system is used in a Swiss tournament?",
    "c35": "In an Armageddon game, who wins if it ends in a draw?",
}
assert set(PERGUNTAS_EN) == {c[0] for c in CASOS}, "PERGUNTAS_EN e CASOS divergem"


def veredito_da_biblioteca(fen: str, lance: str | None) -> str:
    b = chess.Board(fen)
    if lance is None:
        if b.is_stalemate():
            return "afogado"
        if b.is_insufficient_material():
            return "posicao_morta"
        if b.can_claim_fifty_moves():
            return "cinquenta_lances"
        return f"{b.legal_moves.count()}_lances"
    return "legal" if b.is_legal(chess.Move.from_uci(lance)) else "ilegal"


def verificar() -> int:
    falhas = 0
    posicionais = [c for c in CASOS if c[2]]
    print(f"conferindo {len(posicionais)} casos posicionais com python-chess {chess.__version__}\n")
    for cid, _, fen, lance, pergunta, _, ouro, _ in posicionais:
        try:
            obtido = veredito_da_biblioteca(fen, lance)
        except Exception as e:
            print(f"  ERRO {cid}: {type(e).__name__}: {e}")
            falhas += 1
            continue
        ok = obtido == ouro
        falhas += not ok
        print(f"  {'ok ' if ok else 'FALHA'} {cid}  gabarito={ouro:<18} biblioteca={obtido:<18} {pergunta[:44]}")
    print(f"\n{len(posicionais) - falhas}/{len(posicionais)} conferem")
    if falhas:
        print("Gabarito e biblioteca divergem. Nao siga: releia o FEN e o PDF.")
    return falhas


def emitir() -> None:
    destino = AQUI / "suite_30.jsonl"
    with destino.open("w", encoding="utf-8") as f:
        for cid, classe, fen, lance, pergunta, artigos, ouro, parada in CASOS:
            f.write(json.dumps({
                "id": cid, "classe": classe, "fen": fen, "lance": lance,
                "pergunta": PERGUNTAS_EN[cid], "pergunta_pt": pergunta,
                "artigo_ouro": artigos,
                "veredito_ouro": ouro, "parada_esperada": parada,
            }, ensure_ascii=False) + "\n")
    print(f"{destino}: {len(CASOS)} casos")
    for classe in ("posicional", "hibrida", "normativa"):
        print(f"  {classe:12} {sum(1 for c in CASOS if c[1] == classe)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verificar", action="store_true")
    p.add_argument("--emitir", action="store_true")
    a = p.parse_args()
    if a.verificar or not a.emitir:
        sys.exit(1 if verificar() else 0)
    emitir()
