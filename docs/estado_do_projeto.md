# Estado do projeto

Atualizado em 09/11/2026 (noite).

## Decisões de 09/11 (sessão da tarde)

- **Recusa:** a string é `nao consta no material`, sem acento, igual no prompt, na suíte e no grader.
- **3.8.2.2:** os itens `3)` e `4)` são numeração da própria FIDE (conferido no HTML). O parser está certo.
- **Perguntas em inglês** estão em `PERGUNTAS_EN` (`suite/suite_30.py`), congeladas antes de rodar a busca. O texto em português ficou em `pergunta_pt`.
- **c31–c35** (fora de escopo, `recusa`): **rascunho, aguardando revisão humana.** A suíte tem 35 casos; o nome `suite_30` foi mantido.
- **Busca: e5-large** (`intfloat/multilingual-e5-large`). Foi escolhido pela checagem abaixo, com as perguntas já congeladas.
- **Ramo A: Groq, `openai/gpt-oss-120b`, temperatura 0, k=5** (padrões em `src/agente.py`). O `llama-3.3-70b-versatile` não é mais servido: o `/models` do Groq só lista Llama prompt-guard. A primeira chamada real (c12) confirmou `modelo_servido = openai/gpt-oss-120b`. É um modelo de raciocínio: ~420 dos 557 tokens de saída foram de raciocínio.
- **Chave:** `GROQ_API_KEY` fica em `.env` na raiz (no `.gitignore`). O `agente.py` lê esse arquivo.
- **c19/c20 (mate):** o gabarito continua `legal`. A pergunta sobre o mate fica com o humano, que vê `depois.mate` do python-chess na interface (c19: mate; c20: não é mate).

## Busca: artigo_ouro no top-k (29 casos com ouro)

| backend | k=3 | k=5 |
|---|---|---|
| tfidf | 12 | 19 |
| e5-large | 18 | 22 |

Fonte: `resultados/checagem_trechos_*_k*.csv`. A coluna `rotulo` (suficiente/parcial/ausente) está vazia e precisa ser preenchida à mão.

- **c12** com a pergunta final: no e5 a 3.8.2.2 fica em 1º lugar. No TF-IDF ela some do top-3. A checagem "suficiente" anterior usava a consulta no vocabulário da FIDE.
- **Roque (c09–c14)** é o ponto fraco nos dois backends ("castle" ≠ "castling"; os chunks 4.4.x atraem a consulta).

## Pronto

- `src/montar_prompt.py`: trechos primeiro, tabuleiro ASCII, lance em palavras (UCI + peça na origem), sem `--consulta`. O autoteste passa.
- `src/checar_trechos.py`: gera a planilha da checagem humana.
- `src/comparador.py`: função pura; `--demo` dispara as quatro paradas. Pergunta sem FEN não passa por ele (`sem_verificacao`). Nos casos sem lance, a comparação usa a tabela `ACEITA_SEM_LANCE`, que é regra declarada e não juiz.
- `src/agente.py`: pipeline completo com trace em `traces/` e aprovação por `input()`. Só foi testado com `--seco`.
- `src/interface.py` + `interface/index.html` (`bash run.sh interface`): servidor só com a biblioteca padrão, em http://127.0.0.1:8251. Tem duas abas:
  - **Suíte:** tabuleiro, Ramo B, execuções com aprovação, trechos com rótulo, revisão do caso.
  - **Manual:** editor de tabuleiro → FEN → chat com aprovação antes da emissão.
  - Os traces da interface ficam em `traces/interface/` e **não** entram nas 90 execuções.

## Em aberto

- [x] Primeira chamada real ao Groq. c12: o modelo disse `legal`, citou a 3.8.2.2 e a parada foi `concordam` (a suíte esperava discordância). Trace de fumaça descartado.
- [ ] Revisar os 35 casos na aba Revisão da interface (c31–c35 primeiro).
- [ ] Rótulos de trechos (suficiente/parcial/ausente) na aba Trechos → `resultados/rotulos_humanos.json`.
- [ ] Classroom: prazo, páginas, resumo, palavras-chave.
- [x] Repositório: github.com/YagoLX/exameTE251 (branch `main`).
- [ ] Depois: as 90 execuções e `src/grader.py`.
