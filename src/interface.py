#!/usr/bin/env python3
"""
interface.py - interface grafica local (so biblioteca padrao + o que o projeto ja usa).

    python src/interface.py            # abre em http://127.0.0.1:8251
    python src/interface.py --porta 9000 --backend tfidf

Duas abas na pagina (interface/index.html):
  Suite de testes  - percorre os casos: tabuleiro, pergunta, execucoes (traces),
                     trechos recuperados e o formulario de revisao humana.
  Testes manuais   - editor de tabuleiro -> FEN -> chat com o agente.

Onde grava:
  traces/interface/*.json         execucoes disparadas pela interface (NAO entram nas 90)
  resultados/rotulos_humanos.json  rotulos da revisao humana (trechos, resposta, caso)

A pagina mostra o gabarito e o Ramo B ao revisor humano. Isso nao fere a
independencia: o que vai ao modelo continua sendo so montar_prompt.montar().
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agente  # noqa: E402
from buscar_artigo import Indice, E5_MODELO  # noqa: E402
from legalidade import legalidade  # noqa: E402
from montar_prompt import carregar_suite  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = RAIZ / "interface" / "index.html"
TRACES = RAIZ / "traces"
TRACES_GUI = TRACES / "interface"
ROTULOS = RAIZ / "resultados" / "rotulos_humanos.json"
TRAVA = threading.Lock()          # pipeline: um por vez (indice e rate limit)
TRAVA_ROTULOS = threading.Lock()  # separada: gravar rotulo nao espera o modelo
ESTADO: dict = {}


def ler_rotulos() -> dict:
    if ROTULOS.exists():
        return json.loads(ROTULOS.read_text(encoding="utf-8"))
    return {"casos": {}, "traces": {}}


def gravar_rotulo(tipo: str, chave: str, dados: dict) -> dict:
    with TRAVA_ROTULOS:
        r = ler_rotulos()
        r.setdefault(tipo, {})[chave] = {**dados, "em": agente.agora()}
        ROTULOS.parent.mkdir(exist_ok=True)
        ROTULOS.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        return r


def resumo_trace(caminho: Path) -> dict:
    t = json.loads(caminho.read_text(encoding="utf-8"))
    return {"arquivo": str(caminho.relative_to(TRACES)), **t}


def casas_atacadas(fen: str) -> dict:
    """So para desenhar: casas atacadas pelo lado que NAO tem a vez."""
    try:
        b = chess.Board(fen)
    except Exception as e:
        return {"erro": str(e)}
    oponente = not b.turn
    return {"atacadas": [chess.square_name(s) for s in chess.SQUARES if b.is_attacked_by(oponente, s)],
            "valido": b.is_valid(), "status": str(b.status())}


def dados_caso(cid: str) -> dict:
    caso = ESTADO["suite"][cid]
    idx, cfg = ESTADO["idx"], ESTADO["cfg"]
    oficiais = sorted(TRACES.glob(f"{cid}_r*.json"))
    gui = sorted(TRACES_GUI.glob(f"{cid}_*.json")) if TRACES_GUI.exists() else []
    return {
        "caso": caso,
        "ramo_b": legalidade(caso["fen"], caso["lance"]) if caso["fen"] else None,
        "hits": idx.buscar(caso["pergunta"], k=cfg.k),
        "traces": [resumo_trace(p) for p in oficiais + gui],
        "rotulos": ler_rotulos(),
    }


def executar(caso: dict) -> dict:
    with TRAVA:
        t = agente.rodar(caso, ESTADO["idx"], ESTADO["cfg"])
    TRACES_GUI.mkdir(parents=True, exist_ok=True)
    nome = f"{caso['id']}_{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json"
    destino = TRACES_GUI / nome
    destino.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumo_trace(destino)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silencioso, exceto erros
        pass

    def _json(self, obj, status=200):
        corpo = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        try:
            if self.path in ("/", "/index.html"):
                corpo = PAGINA.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
            elif self.path == "/api/suite":
                cfg = ESTADO["cfg"]
                self._json({"casos": list(ESTADO["suite"].values()), "rotulos": ler_rotulos(),
                            "config": {"modelo": cfg.modelo, "k": cfg.k, "backend": cfg.backend,
                                       "temperatura": cfg.temperatura, "seco": cfg.seco}})
            elif self.path.startswith("/api/caso/"):
                cid = self.path.rsplit("/", 1)[-1]
                if cid not in ESTADO["suite"]:
                    return self._json({"erro": f"caso {cid} nao existe"}, 404)
                self._json(dados_caso(cid))
            else:
                self._json({"erro": "rota desconhecida"}, 404)
        except Exception as e:
            self._json({"erro": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self):
        try:
            d = self._corpo()
            if self.path == "/api/rodar":
                if d.get("id") in ESTADO["suite"]:
                    caso = ESTADO["suite"][d["id"]]
                else:
                    pergunta = (d.get("pergunta") or "").strip()
                    if not pergunta:
                        return self._json({"erro": "pergunta vazia"}, 400)
                    caso = {"id": "manual", "pergunta": pergunta,
                            "fen": (d.get("fen") or "").strip() or None,
                            "lance": (d.get("lance") or "").strip().lower() or None}
                self._json(executar(caso))
            elif self.path == "/api/aprovar":
                caminho = (TRACES / d["arquivo"]).resolve()
                if TRACES.resolve() not in caminho.parents or not caminho.exists():
                    return self._json({"erro": "trace invalido"}, 400)
                if d.get("decisao") not in ("aprovado", "rejeitado", "revisao_humana"):
                    return self._json({"erro": "decisao invalida"}, 400)
                t = agente.registrar_aprovacao(caminho, d["decisao"], "interface")
                self._json({"arquivo": d["arquivo"], **t})
            elif self.path == "/api/rotulo":
                if d.get("tipo") not in ("casos", "traces"):
                    return self._json({"erro": "tipo invalido"}, 400)
                self._json(gravar_rotulo(d["tipo"], d["chave"], d.get("dados", {})))
            elif self.path == "/api/atacadas":
                self._json(casas_atacadas(d.get("fen", "")))
            else:
                self._json({"erro": "rota desconhecida"}, 404)
        except Exception as e:
            self._json({"erro": f"{type(e).__name__}: {e}"}, 500)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--porta", type=int, default=8251)
    p.add_argument("--provedor", default=agente.PROVEDOR_PADRAO, choices=list(agente.PROVEDORES))
    p.add_argument("--modelo", default=agente.MODELO_PADRAO)
    p.add_argument("--temperatura", type=float, default=0.0)
    p.add_argument("--backend", default=agente.BACKEND_PADRAO, choices=["tfidf", "e5"])
    p.add_argument("--modelo-e5", default=E5_MODELO)
    p.add_argument("-k", type=int, default=agente.K_PADRAO)
    p.add_argument("--seco", action="store_true", help="nao chama a API (testa a interface)")
    a = p.parse_args()

    ESTADO["cfg"] = SimpleNamespace(provedor=a.provedor, modelo=a.modelo, temperatura=a.temperatura, k=a.k,
                                    backend=a.backend, seco=a.seco, execucao="interface")
    ESTADO["suite"] = carregar_suite()
    print(f"carregando indice {a.backend}...")
    ESTADO["idx"] = Indice.carregar(a.backend, a.modelo_e5)
    ESTADO["idx"].buscar("warm up", k=1)       # carrega o e5 antes do primeiro clique
    srv = ThreadingHTTPServer(("127.0.0.1", a.porta), Handler)
    print(f"interface em http://127.0.0.1:{a.porta}   (Ctrl+C para sair)"
          + ("   [modo seco: sem API]" if a.seco else ""))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
