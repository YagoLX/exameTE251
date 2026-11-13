# Estado do projeto

Atualizado em 12/11/2026.

## 12/11: grader rodado sobre os 105 traces oficiais

- `python3 src/grader.py` → `resultados/grader_execucoes.csv`, `grader_resumo.json`, `grader_resumo.md`. Configuração única nas 105 (`qwen3:8b`, temperatura 0, k=5, e5); prompt idêntico nas 3 repetições em 35/35 casos.
- Critérios (execuções / pass^3 em casos): citação identificável 72/81 e 24/27 (falham c04, c12, c17); trecho citado presente nos trechos 81/81 e 27/27; recusa correta 96/105 e 32/35 (falham c22, c24, c29).
- Posicionais: 39 `concordam`, 30 `discordam`, 3 `recusa`. Nas 30 discordâncias errou sempre o Ramo A (o Ramo B bate com o gabarito em 72/72). c11, c14 e c16 concordaram sem nenhum artigo do gabarito nos trechos.
- As execuções oficiais rodaram em lote e não emitiram nada: a saída de cada uma é o trace. A revisão humana veio depois (seção abaixo).

## 11/11: revisão humana dos casos

Feita na interface e gravada em `resultados/rotulos_humanos.json`, com o gabarito e o Ramo B à vista do revisor.

- **Trechos recuperados**, nos 35 casos: 15 `suficiente`, 8 `parcial`, 12 `ausente` (os 5 fora de escopo são `ausente` por construção).
- **Revisão do caso**, com nota: 26 `ok`, 4 `ajustar`, 1 `remover`.
- **Achados**, declarados como limitação (a suíte fica congelada depois das execuções):
  - c06: o gabarito tem só o 3.7.3.3; a pergunta combina captura e promoção, então o 3.7.3 também caberia.
  - c20: o gabarito `legal` mede a legalidade do lance, mas a pergunta é se o lance dá mate (não dá).
  - c22: a resposta depende de conhecimento de xadrez que o corpus não traz (a regra de posição morta é genérica).
  - c27: o 7.6 também cobre o caso e poderia ser ouro secundário.
  - c31: fora de escopo; a busca trouxe o roque padrão (3.8.2) em 1º e o modelo recusou mesmo assim.

## Decisão de 11/11: modelo local no Ramo A

- **Ramo A: Ollama, `qwen3:8b`, temperatura 0, `seed=0`, raciocínio desligado, k=5** (padrões em `src/agente.py`; `--provedor ollama`). Roda em CPU na máquina do projeto, sem chave e sem rede.
- **Por quê:** (1) o primeiro modelo escolhido (`openai/gpt-oss-120b` no Groq) saiu do ar em 10/11 (404 em todos os endpoints, inclusive `/models`), e as alternativas gratuitas na nuvem dependem de cota e de terceiros; (2) o modelo local é estável e reproduzível: o modelo e a versão não mudam durante as 105 execuções, e nenhuma pergunta sai da máquina; (3) custo zero; (4) pelo que vimos no teste de fumaça, é suficiente para o objetivo do trabalho, que é medir a *discordância entre os ramos*, não maximizar a acurácia do Ramo A.
- **Teste de fumaça (c12, c02, c03):** ~70–110 s por execução. c12: `ilegal` contra `legal` do Ramo B → `discordam` (o caso foi desenhado para isso). c02 e c03: `concordam`.
- **Limitações:** modelo de 8B é mais fraco que o 120B e pode errar mais a leitura da regra (isso aumenta a discordância, que é o que o comparador mede); não-determinismo residual em CPU não está descartado, por isso o pass^3 é medido.
- Os registros abaixo sobre Groq são anteriores a esta decisão.

## Decisões de 09/11 (sessão da tarde)

- **Recusa:** a string é `nao consta no material`, sem acento, igual no prompt, na suíte e no grader.
- **3.8.2.2:** os itens `3)` e `4)` são numeração da própria FIDE (conferido no HTML). O parser está certo.
- **Perguntas em inglês** estão em `PERGUNTAS_EN` (`suite/suite_30.py`), congeladas antes de rodar a busca. O texto em português ficou em `pergunta_pt`.
- **c31–c35** (fora de escopo, `recusa`) entram na suíte, que tem 35 casos; o nome `suite_30` foi mantido. Foram revisados em 11/11.
- **Busca: e5-large** (`intfloat/multilingual-e5-large`). Foi escolhido pela checagem abaixo, com as perguntas já congeladas.
- **Ramo A (depois substituído em 11/11): Groq, `openai/gpt-oss-120b`.** O `llama-3.3-70b-versatile` não era mais servido. A primeira chamada real (c12) confirmou `modelo_servido = openai/gpt-oss-120b`.
- **Chave de nuvem:** quando se usa `--provedor groq` ou `openrouter`, a chave fica em `.env` na raiz (no `.gitignore`).
- **c19/c20 (mate):** o gabarito é `legal` (a legalidade do lance). Se o lance dá mate aparece em `depois.mate` do python-chess (c19: mate; c20: não é mate).

## Busca: artigo_ouro no top-k (29 casos com ouro)

| backend | k=3 | k=5 |
|---|---|---|
| tfidf | 12 | 19 |
| e5-large | 18 | 22 |

Fonte: `resultados/checagem_trechos_*_k*.csv`. O rótulo humano dos trechos está em `resultados/rotulos_humanos.json`.

- **c12** com a pergunta final: no e5 a 3.8.2.2 fica em 1º lugar. No TF-IDF ela some do top-3.
- **Roque (c09–c14)** é o ponto fraco nos dois backends ("castle" ≠ "castling"; os chunks 4.4.x atraem a consulta).

## Verificação de vazamento (09/11)

**Sem vazamento em código:**
- O prompt dos 35 casos não contém gabarito nem saída do Ramo B. Os termos achados (`checkmate`, `legal`) vêm das próprias perguntas.
- O autoteste também proíbe chamadas de legalidade do `chess` dentro de `montar_prompt.py`.
- Os traces gravados têm prompt idêntico ao de `montar()`.

**Limitações declaradas:**
1. **Premissas nas perguntas.** c10, c11, c14 e c17 afirmam o fato decisivo ("I'm in check", "rook is hitting f1"). Essas premissas já estavam no gabarito em português. O Ramo A testa a *leitura da regra dada a premissa*, não a leitura do tabuleiro.
2. **c18: premissa introduzida na tradução.** "right next to the other king" não existe no original em português ("O rei pode avancar para d2?") e aponta para a resposta. A pergunta foi mantida como estava nas execuções.
3. **Seleção no conjunto de teste.** O backend e o k foram escolhidos com o `artigo_ouro` da suíte, então 22/29 é otimista. Contraprova independente (`resultados/recall_e5.csv`, 10 consultas próprias): e5 9/10 EN e 8/10 PT; TF-IDF 7/10 EN e 1/10 PT.
4. **`ACEITA_SEM_LANCE`** foi escrita conhecendo as perguntas c21–c23.
5. **Contaminação do modelo.** O modelo pode ter visto as Leis da FIDE no treino e acertar de memória. Exigir que a citação venha dos trechos mitiga, mas não elimina.
6. **Revisor vê o gabarito e o Ramo B** na interface ao rotular: risco de viés de confirmação.

## Componentes

- `src/montar_prompt.py`: trechos primeiro, tabuleiro ASCII, lance em palavras (UCI + peça na origem). O autoteste passa.
- `src/checar_trechos.py`: planilha do top-k por caso, com o artigo do gabarito conferido em código.
- `src/comparador.py`: função pura; dispara as quatro paradas sob demanda. Pergunta sem FEN não passa por ele (`sem_verificacao`). Nos casos sem lance, a comparação usa a tabela `ACEITA_SEM_LANCE`, que é regra declarada e não juiz.
- `src/agente.py`: pipeline completo; grava o trace em `traces/` e não emite nada. Gerou as 105 execuções oficiais.
- `src/grader.py`: critérios automáticos, pass^3 medido, discordâncias e resumo da revisão humana.
- `src/interface.py` + `interface/index.html` (`bash run.sh interface`): servidor só com a biblioteca padrão, em http://127.0.0.1:8251. Tem duas abas:
  - **Suíte:** tabuleiro, Ramo B, execução de um caso, rótulo dos trechos e revisão do caso.
  - **Manual:** editor de tabuleiro → FEN → chat; o revisor vê o trace e decide se a resposta aparece.
  - Os traces da interface ficam em `traces/interface/` e **não** entram nas 105 execuções oficiais.
- Repositório: github.com/YagoLX/exameTE251 (branch `main`).
