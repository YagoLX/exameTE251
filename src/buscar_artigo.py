#!/usr/bin/env python3
"""
buscar_artigo.py - a autoridade normativa (Ramo A do sistema).

Indexa corpus/chunks.jsonl e recupera as k clausulas mais proximas de uma consulta.
Dois backends, com a MESMA interface, para que a troca seja uma medicao e nao uma reforma:

  tfidf  - TfidfVectorizer do scikit-learn, lexico. Zero download, roda offline.
  e5     - sentence-transformers com intfloat/multilingual-e5-base, denso e multilingue.
           Baixa ~1 GB na primeira vez.

Uso:
    python buscar_artigo.py --indexar                      # constroi o indice (tfidf)
    python buscar_artigo.py --indexar --backend e5
    python buscar_artigo.py "pode rocar estando em xeque?"
    python buscar_artigo.py --backend e5 -k 5 "en passant"

Como biblioteca:
    from buscar_artigo import Indice
    idx = Indice.carregar(backend="tfidf")
    hits = idx.buscar("pode rocar estando em xeque?", k=3)
    # hits = [{"artigo": "3.8.2.2", "texto": ..., "score": 0.41}, ...]
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
CHUNKS = RAIZ / "corpus" / "chunks.jsonl"
INDICE = RAIZ / "indice"

# O model card do intfloat/e5 manda prefixar consulta e documento.
# CONFIRA no model card antes de publicar numeros: esquecer o prefixo degrada a busca.
E5_MODELO = "intfloat/multilingual-e5-base"
E5_PREFIXO_CONSULTA = "query: "
E5_PREFIXO_DOC = "passage: "


def carregar_chunks() -> list[dict]:
    if not CHUNKS.exists():
        sys.exit(f"ERRO: {CHUNKS} nao existe. Rode antes:\n"
                 f"  python3 parse_fide.py corpus/fide_handbook_E012023.html")
    chunks = [json.loads(l) for l in CHUNKS.open(encoding="utf-8") if l.strip()]
    if not chunks:
        sys.exit(f"ERRO: {CHUNKS} esta vazio.")
    return chunks


class Indice:
    def __init__(self, backend: str, chunks: list[dict], matriz, vetorizador=None):
        self.backend = backend
        self.chunks = chunks
        self.matriz = matriz          # (n_chunks, dim), linhas normalizadas
        self.vetorizador = vetorizador

    # ---------- construcao ----------

    @classmethod
    def construir(cls, backend: str) -> "Indice":
        chunks = carregar_chunks()
        textos = [c["texto_indexado"] for c in chunks]

        if backend == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            vet = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), min_df=1)
            m = vet.fit_transform(textos).toarray().astype(np.float32)
            m = cls._normalizar(m)
            return cls(backend, chunks, m, vet)

        if backend == "e5":
            from sentence_transformers import SentenceTransformer
            modelo = SentenceTransformer(E5_MODELO)
            m = modelo.encode([E5_PREFIXO_DOC + t for t in textos],
                              batch_size=16, show_progress_bar=True,
                              normalize_embeddings=True).astype(np.float32)
            return cls(backend, chunks, m, None)

        sys.exit(f"ERRO: backend desconhecido: {backend}")

    @staticmethod
    def _normalizar(m: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(m, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return m / n

    def salvar(self) -> None:
        INDICE.mkdir(exist_ok=True)
        np.save(INDICE / f"matriz_{self.backend}.npy", self.matriz)
        with (INDICE / f"meta_{self.backend}.pkl").open("wb") as f:
            pickle.dump({"chunks": self.chunks, "vetorizador": self.vetorizador}, f)
        meta = {
            "backend": self.backend,
            "modelo": E5_MODELO if self.backend == "e5" else "sklearn TfidfVectorizer(sublinear_tf, 1-2gram)",
            "n_chunks": len(self.chunks),
            "dim": int(self.matriz.shape[1]),
            "doc_id": self.chunks[0].get("doc_id"),
            "edicao": self.chunks[0].get("edicao"),
        }
        (INDICE / f"indice_{self.backend}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(meta, ensure_ascii=False, indent=2))

    @classmethod
    def carregar(cls, backend: str = "tfidf") -> "Indice":
        mp = INDICE / f"matriz_{backend}.npy"
        if not mp.exists():
            sys.exit(f"ERRO: indice '{backend}' nao construido. Rode:\n"
                     f"  python3 buscar_artigo.py --indexar --backend {backend}")
        m = np.load(mp)
        with (INDICE / f"meta_{backend}.pkl").open("rb") as f:
            d = pickle.load(f)
        return cls(backend, d["chunks"], m, d["vetorizador"])

    # ---------- busca ----------

    def _vetor_consulta(self, consulta: str) -> np.ndarray:
        if self.backend == "tfidf":
            v = self.vetorizador.transform([consulta]).toarray().astype(np.float32)
            return self._normalizar(v)[0]
        from sentence_transformers import SentenceTransformer
        if not hasattr(self, "_modelo"):
            self._modelo = SentenceTransformer(E5_MODELO)
        return self._modelo.encode([E5_PREFIXO_CONSULTA + consulta],
                                   normalize_embeddings=True).astype(np.float32)[0]

    def buscar(self, consulta: str, k: int = 3) -> list[dict]:
        """Devolve os k chunks mais proximos. Linhas e consulta sao normalizadas,
        entao o produto interno JA E o cosseno."""
        q = self._vetor_consulta(consulta)
        scores = self.matriz @ q
        ordem = np.argsort(-scores)[:k]
        saida = []
        for i in ordem:
            c = self.chunks[int(i)]
            saida.append({
                "artigo": c["artigo"],
                "texto": c["texto"],
                "artigo_titulo": c.get("artigo_titulo"),
                "score": round(float(scores[int(i)]), 4),
            })
        return saida


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("consulta", nargs="?", help="pergunta a buscar")
    p.add_argument("--indexar", action="store_true", help="construir o indice e sair")
    p.add_argument("--backend", default="tfidf", choices=["tfidf", "e5"])
    p.add_argument("-k", type=int, default=3, help="quantos chunks devolver (padrao 3)")
    p.add_argument("--json", action="store_true", help="saida em JSON")
    a = p.parse_args()

    if a.indexar:
        Indice.construir(a.backend).salvar()
        return

    if not a.consulta:
        p.error("informe uma consulta, ou use --indexar")

    hits = Indice.carregar(a.backend).buscar(a.consulta, k=a.k)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return
    print(f"consulta: {a.consulta}   [backend={a.backend}, k={a.k}]")
    for h in hits:
        print(f"\n  [{h['score']:.4f}] Artigo {h['artigo']}  ({h['artigo_titulo']})")
        for linha in h["texto"].split("\n"):
            print(f"      {linha[:150]}")


if __name__ == "__main__":
    main()