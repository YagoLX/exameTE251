#!/usr/bin/env bash
set -euo pipefail
case "${1:-ajuda}" in
  corpus)  python3 src/parse_fide.py corpus/fide_handbook_E012023.html ;;
  indice)  python3 src/buscar_artigo.py --indexar --backend "${2:-tfidf}" ;;
  recall)  python3 src/experimento_recall.py --backend "${2:-tfidf}" \
             --csv "resultados/recall_${2:-tfidf}.csv" ;;
  tudo)    bash run.sh corpus && bash run.sh indice tfidf && bash run.sh recall tfidf ;;
  *) echo "uso: bash run.sh {corpus|indice [tfidf|e5]|recall [tfidf|e5]|tudo}" ;;
esac
