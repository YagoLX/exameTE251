# Estado do projeto

Atualizado em 11/11/2026.

## Decisão de 11/11: modelo local no Ramo A

- **Ramo A: Ollama, `qwen3:8b`, temperatura 0, `seed=0`, raciocínio desligado, k=5** (padrões em `src/agente.py`; `--provedor ollama`). Roda em CPU na máquina do projeto, sem chave e sem rede.
- **Por quê:** (1) o primeiro modelo escolhido (`openai/gpt-oss-120b` no Groq) saiu do ar em 10/11 (404 em todos os endpoints, inclusive `/models`), e as alternativas gratuitas na nuvem dependem de cota e de terceiros; (2) o modelo local é estável e reproduzível: o modelo e a versão não mudam durante as 105 execuções, e nenhuma pergunta sai da máquina; (3) custo zero; (4) pelo que vimos no teste de fumaça, é suficiente para o objetivo do trabalho, que é medir a *discordância entre os ramos*, não maximizar a acurácia do Ramo A.
- **Teste de fumaça (c12, c02, c03):** ~70–110 s por execução. c12: `ilegal` contra `legal` do Ramo B → `discordam` (o caso foi desenhado para isso). c02 e c03: `concordam`. Três casos não medem qualidade; a taxa de discordância virá das execuções oficiais.
- **Limitações a declarar:** modelo de 8B é mais fraco que o 120B e pode errar mais a leitura da regra (isso aumenta a discordância, que é o que o comparador mede); não-determinismo residual em CPU não está descartado, por isso o pass^3 é medido; o `gpt-oss-120b` ficou só como execução complementar se o Groq voltar (um único caso, c12, foi testado: `legal`, `concordam`).
- Os registros abaixo sobre Groq são anteriores a esta decisão.

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

## Verificação de vazamento (09/11)

**Sem vazamento em código:**
- O prompt dos 35 casos não contém gabarito nem saída do Ramo B. Os termos achados (`checkmate`, `legal`) vêm das próprias perguntas.
- O autoteste agora também proíbe chamadas de legalidade do `chess` dentro de `montar_prompt.py`.
- Os traces gravados têm prompt idêntico ao de `montar()`.

**A declarar no artigo:**
1. **Premissas nas perguntas.** c10, c11, c14 e c17 afirmam o fato decisivo ("I'm in check", "rook is hitting f1"). Essas premissas já estavam no gabarito em português. O Ramo A testa a *leitura da regra dada a premissa*, não a leitura do tabuleiro.
2. **c18: premissa introduzida na tradução.** "right next to the other king" não existe no original em português ("O rei pode avancar para d2?") e aponta para a resposta. Decisão pendente.
3. **Seleção no conjunto de teste.** O backend e o k foram escolhidos com o `artigo_ouro` da suíte, então 22/29 é otimista. Contraprova independente (`resultados/recall_e5.csv`, 10 consultas próprias): e5 9/10 EN e 8/10 PT; TF-IDF 7/10 EN e 1/10 PT.
4. **`ACEITA_SEM_LANCE`** foi escrita conhecendo as perguntas c21–c23.
5. **Contaminação do modelo.** O gpt-oss provavelmente viu as Leis da FIDE no treino e pode acertar de memória. O critério "citação nos trechos" mitiga, mas não elimina. A sonda possível: rodar com trechos irrelevantes e ver se ele recusa.
6. **Revisor vê o gabarito e o Ramo B** na interface ao rotular "resposta correta": risco de viés de confirmação.

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
