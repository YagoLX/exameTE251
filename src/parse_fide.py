#!/usr/bin/env python3
"""
parse_fide.py - transforma o HTML das Leis do Xadrez da FIDE em chunks,
um por clausula numerada, com a hierarquia preservada.

Uso:
    python parse_fide.py corpus/fide_handbook_E012023.html

Escreve:
    corpus/chunks.jsonl      - um chunk por linha (o indice e construido daqui)
    corpus/glossario.jsonl   - o Glossario, separado e NAO indexado
    corpus/relatorio.txt     - contagens para conferencia humana
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

NUMERO = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$", re.S)


class ColetorFIDE(HTMLParser):
    """Coleta <p class="HBLevel*"> e as celulas de <p class="HBTable3">."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragrafos = []          # (classe, texto, tinha_img)
        self._classe = None
        self._buf = []
        self._img = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "p":
            classe = d.get("class", "")
            if classe.startswith("HB"):
                self._classe = classe
                self._buf = []
                self._img = False
        elif tag == "img" and self._classe:
            self._img = True

    def handle_endtag(self, tag):
        if tag == "p" and self._classe:
            texto = " ".join("".join(self._buf).split())
            self.paragrafos.append((self._classe, texto, self._img))
            self._classe = None
            self._buf = []
            self._img = False

    def handle_data(self, data):
        if self._classe:
            self._buf.append(data)


def parse(caminho: Path):
    coletor = ColetorFIDE()
    coletor.feed(caminho.read_text(encoding="utf-8", errors="replace"))

    chunks = []
    glossario = []
    atual = None
    artigo_titulo = None
    orfaos = 0
    imagens = 0

    for classe, texto, tinha_img in coletor.paragrafos:
        if classe == "HBTable3":
            glossario.append(texto)
            continue
        if tinha_img:
            imagens += 1
            if not texto:
                continue
        if not texto:
            continue

        nivel = int(re.sub(r"\D", "", classe.replace("nonumber", "")) or 0)

        if classe.endswith("nonumber"):
            # continuacao: pertence a ultima clausula numerada aberta
            if atual is None:
                orfaos += 1
                continue
            atual["texto"] += "\n" + texto
            continue

        m = NUMERO.match(texto)
        if m:
            numero, corpo = m.group(1), m.group(2).strip()
        else:
            # Article N: ... / BASIC RULES OF PLAY / Appendix X
            numero, corpo = None, texto
            if re.match(r"^(Article \d+|Appendix [A-Z]|Guidelines)", texto):
                artigo_titulo = texto

        if atual is not None:
            chunks.append(atual)
        atual = {
            "artigo": numero,
            "titulo": corpo if numero is None else None,
            "nivel": nivel,
            "pai": ".".join(numero.split(".")[:-1]) if numero and "." in numero else None,
            "texto": corpo,
            "artigo_titulo": artigo_titulo,
        }

    if atual is not None:
        chunks.append(atual)

    return chunks, glossario, orfaos, imagens


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    origem = Path(sys.argv[1])
    saida = origem.parent

    chunks, glossario, orfaos, imagens = parse(origem)

    numerados = [c for c in chunks if c["artigo"]]
    sem_numero = [c for c in chunks if not c["artigo"]]

    if not numerados:
        print(f"ERRO: nenhuma clausula numerada encontrada em {origem.name}.", file=sys.stderr)
        print("Esta fonte nao usa a marcacao HBLevel do handbook da FIDE.", file=sys.stderr)
        print("Nada foi escrito: os arquivos de saida existentes estao intactos.", file=sys.stderr)
        sys.exit(2)

    with (saida / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for i, c in enumerate(numerados):
            c["chunk_id"] = i
            c["doc_id"] = "FIDE-Laws-of-Chess"
            c["edicao"] = "em vigor desde 01/01/2023"
            cabecalho = c["artigo_titulo"] or ""
            c["texto_indexado"] = f"{cabecalho} - {c['artigo']} {c['texto']}".strip(" -")
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    with (saida / "glossario.jsonl").open("w", encoding="utf-8") as f:
        for linha in glossario:
            if linha:
                f.write(json.dumps({"texto": linha}, ensure_ascii=False) + "\n")

    por_nivel = {}
    for c in numerados:
        por_nivel[c["nivel"]] = por_nivel.get(c["nivel"], 0) + 1
    comprimentos = sorted(len(c["texto"]) for c in numerados)
    vazios = [c["artigo"] for c in numerados if len(c["texto"]) < 40]

    linhas = [
        f"origem: {origem.name}",
        f"chunks numerados: {len(numerados)}",
        f"blocos sem numero (titulos de Artigo, Apendices): {len(sem_numero)}",
        f"linhas de glossario (NAO indexadas): {len(glossario)}",
        f"paragrafos com imagem: {imagens}",
        f"continuacoes orfas (deveria ser 0): {orfaos}",
        "chunks por nivel: " + ", ".join(f"n{k}={v}" for k, v in sorted(por_nivel.items())),
        f"tamanho do texto: min={comprimentos[0]} mediana={comprimentos[len(comprimentos)//2]} max={comprimentos[-1]}",
        f"chunks com menos de 40 caracteres ({len(vazios)}): {', '.join(vazios[:20])}",
    ]
    relatorio = "\n".join(linhas)
    (saida / "relatorio.txt").write_text(relatorio + "\n", encoding="utf-8")
    print(relatorio)

    print("\n--- conferencia manual: artigos que a suite usa ---")
    alvo = ["3.7.3.2", "3.8.2.1", "3.8.2.2", "3.9.2", "5.2.2", "6.9", "7.5.5", "9.3", "11.3.2"]
    achados = {c["artigo"]: c["texto"] for c in numerados}
    for a in alvo:
        t = achados.get(a)
        print(f"{a:9} {'FALTA' if t is None else t[:110].replace(chr(10), ' / ')}")


if __name__ == "__main__":
    main()