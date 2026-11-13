# Assistente de regras de xadrez com duas autoridades

Projeto final da disciplina TE-251 (ITA, 2026.2). Apresentação em **13/11/2026**.

Um assistente que responde dúvidas sobre as regras do xadrez, como *"posso rocar se a casa b1 está atacada?"*, a partir de **duas fontes que não se comunicam**:

| | Ramo A: normativo | Ramo B: factual |
|---|---|---|
| Pergunta que responde | *Qual é a regra?* | *O que é legal nesta posição?* |
| Como | RAG sobre as Leis do Xadrez da FIDE + LLM | [`python-chess`](https://python-chess.readthedocs.io/) 1.11.2, sem LLM |
| Saída | veredito + artigo citado + trecho | veredito determinístico (legal, ilegal, mate, afogado…) |

Os ramos só se encontram no **comparador**, que é código puro, sem IA. Ele devolve uma de quatro paradas: `concordam`, `discordam`, `erro` ou `recusa`. O resultado que o artigo mede é a **taxa de discordância** e **quem estava errado** quando os ramos discordaram.

### O que é um RAG?

*Retrieval-Augmented Generation*, ou geração aumentada por recuperação. Em vez de deixar o modelo de linguagem responder de memória, o sistema faz duas coisas antes:

1. **Recupera** os trechos mais relevantes de um corpus. Aqui o corpus são as 210 cláusulas das Leis da FIDE, e a busca é por similaridade de vetores (embeddings).
2. **Entrega** esses trechos ao modelo junto com a pergunta e exige que ele responda *só* com base neles, citando o artigo.

Assim a resposta fica ancorada num texto verificável. Se os trechos não respondem a pergunta, o modelo deve dizer exatamente `nao consta no material`.

O RAG, porém, não garante que o modelo *leu* a regra direito. É por isso que existe o Ramo B: em perguntas sobre uma posição concreta, um motor de regras independente confere o veredito.

---

## Estado atual (12/11/2026)

### Feito

- **Corpus:** Leis do Xadrez da FIDE em vigor desde 01/01/2023, baixadas do handbook oficial (`corpus/PROVENIENCIA.txt` tem a URL e o SHA-256). O parser gera um trecho (chunk) por cláusula numerada, 210 no total. O Glossário fica fora do índice.
- **Busca:** foram comparados dois backends com as perguntas da suíte já congeladas:

  | backend | artigo certo no top-3 | artigo certo no top-5 |
  |---|---|---|
  | TF-IDF (léxico) | 12/29 | 19/29 |
  | **e5-large** (denso, multilíngue) | **18/29** | **22/29** |

  O escolhido foi o **e5-large com k=5**. O ponto fraco são as perguntas de roque: "castle" não casa com "castling", e os chunks do Artigo 4.4 atraem a consulta.
- **Suíte de avaliação:** 35 casos, todos com pergunta em inglês:
  - 24 posicionais: en passant, promoção, roque, xeque, fim de partida.
  - 6 que só o corpus responde.
  - 5 fora de escopo, em rascunho.

  O gabarito (`veredito_ouro`, `artigo_ouro`) é **humano**. O `python-chess` só confere os 24 posicionais e hoje bate em 24/24.
- **Prompt do Ramo A:** os trechos vêm primeiro, depois o tabuleiro em ASCII, o lance descrito em palavras e por fim instruções curtas. Um **autoteste** prova que o prompt não contém nada do Ramo B nem do gabarito.
- **Comparador**, **agente** (o pipeline completo, com trace JSON e aprovação humana) e **interface gráfica** local.
- **Revisão humana dos 35 casos** feita na interface (rótulos de caso, trechos e resposta correta, em `resultados/rotulos_humanos.json`). Dois ajustes de gabarito na suíte, declarados: `parada_esperada` do c25 passou a `sem_verificacao` e a do c28 a `recusa`, porque casos sem FEN não passam pelo comparador.
- **Execuções oficiais concluídas em 11/11/2026:** 35 casos × 3 repetições, com tudo fixo (`qwen3:8b` local, e5, k=5, temperatura 0, `seed=0`). Os traces estão em `traces/` (e as execuções exploratórias da interface em `traces/interface/`, fora da contagem). As respostas consolidadas estão em `resultados/respostas_execucoes_oficiais.csv`, gerado por `python3 src/exportar_respostas.py`. O arquivo tem as 105 execuções.
- **Grader (`src/grader.py`), rodado em 12/11/2026** sobre os 105 traces oficiais, sem IA. Grava `resultados/grader_execucoes.csv`, `grader_resumo.json` e `grader_resumo.md`. Principais números:

  | | execuções | pass^3 (casos) |
  |---|---|---|
  | citação identificável (número exato de um trecho recuperado) | 72/81 | 24/27 |
  | trecho citado presente nos trechos recuperados | 81/81 | 27/27 |
  | recusa correta | 96/105 | 32/35 |
  | revisão humana registrada no trace | 2/105 | 0/35 |
  | veredito do Ramo A = gabarito (posicionais) | 39/72 | 13/24 |
  | veredito do Ramo B = gabarito (posicionais) | 72/72 | 24/24 |

  Posicionais: 39 `concordam`, 30 `discordam` (10 casos), 3 `recusa` (c22). Nas 30 discordâncias, quem errou foi sempre o Ramo A. c11, c14 e c16 concordaram sem nenhum artigo do gabarito entre os trechos. Variaram entre repetições só c02 e c16 (artigo citado). **Aprovação:** as execuções oficiais rodaram em lote, sem terminal; 103 de 105 ficaram com aprovação `pendente` (nada foi emitido) e 2 foram rejeitadas na interface. A revisão humana foi feita por rótulos de caso, não aprovando cada trace oficial.
- **Modelo do Ramo A:** `qwen3:8b` local, via [Ollama](https://ollama.com), temperatura 0, `seed=0`, raciocínio desligado. A escolha inicial foi `openai/gpt-oss-120b` no Groq, que saiu do ar em 10/11/2026 (404 em todos os endpoints). O modelo local é estável (o modelo não muda durante as execuções), reproduzível, gratuito e não envia nada para fora; no teste de fumaça levou 70–110 s por execução e foi suficiente para o objetivo, que é medir a discordância entre os ramos. Detalhes e limitações em `docs/estado_do_projeto.md`. Os provedores Groq e OpenRouter continuam disponíveis com `--provedor`.

---

## Como rodar

### Instalação

```bash
git clone https://github.com/YagoLX/exameTE251.git && cd exameTE251
python3 -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Instale o [Ollama](https://ollama.com), suba o servidor (`ollama serve`) e baixe o modelo: `ollama pull qwen3:8b` (~5 GB). Não precisa de chave. Para usar a nuvem no lugar (`--provedor groq` ou `openrouter`), crie um `.env` na raiz com a chave do provedor (ele já está no `.gitignore` e nunca deve ir para o repositório).

```
GROQ_API_KEY=gsk_...
```

O índice de busca não está no git. Construa-o uma vez (a primeira execução baixa ~2 GB do modelo e5):

```bash
bash run.sh indice e5        # e, se quiser comparar: bash run.sh indice tfidf
```

### Testes e checagens (nenhum chama o modelo de linguagem)

```bash
bash run.sh suite                          # confere o gabarito contra o python-chess (24/24) e roda o Ramo B
python3 src/montar_prompt.py --autoteste   # invariantes de independência dos ramos
python3 src/comparador.py                  # dispara as quatro paradas do comparador
python3 src/checar_trechos.py --backend e5 -k 5   # planilha de checagem dos trechos recuperados
python3 src/agente.py c12 --seco           # pipeline completo sem chamar a API
```

### Rodar o agente

```bash
python3 src/agente.py c12 --execucao 1                 # um caso
for n in 1 2 3; do python3 src/agente.py --todos --execucao $n; done   # as execuções oficiais
```

Cada execução grava `traces/<caso>_r<n>.json` e pede, no terminal, a aprovação humana (s/n) antes de emitir o veredito. Um trace existente nunca é sobrescrito.

### Interface gráfica

```bash
bash run.sh interface          # http://127.0.0.1:8251
bash run.sh interface --seco   # sem chamar o modelo (ensaio)
```

- **Suíte de testes:**
  - percorre os casos com as setas do teclado;
  - mostra o tabuleiro com o lance em verde e, opcionalmente, as casas atacadas em vermelho;
  - mostra o veredito do python-chess, incluindo se o lance dá mate;
  - roda o agente e aprova ou rejeita cada resposta;
  - permite rotular os trechos recuperados (suficiente/parcial/ausente) e revisar o caso.
- **Testes manuais:**
  - editor de tabuleiro: mover, remover e adicionar peças, importar ou exportar FEN;
  - modo para definir o lance com dois cliques;
  - chat em que cada resposta só é emitida depois de aprovação.

Os rótulos vão para `resultados/rotulos_humanos.json`. As execuções feitas pela interface vão para `traces/interface/` e **não** entram na contagem oficial.

---

## Como funciona

```
pergunta (+ FEN + lance UCI)
   │
   ├─ classe, decidida em código: tem FEN? → posicional; senão → normativa
   │
   ├─ Ramo A ─ buscar_artigo (e5, top-5) → montar_prompt → Ollama (qwen3:8b) → JSON
   │                                                      {veredito, artigo, trecho_citado, justificativa}
   ├─ Ramo B ─ legalidade(fen, lance) com python-chess   → {veredito, flags, depois: {xeque, mate}}
   │
   ├─ comparador(A, B) → concordam | discordam | erro | recusa
   │     (pergunta sem FEN não tem o que comparar → sem_verificacao)
   │
   ├─ trace JSON (prompt + sha256, trechos, resposta bruta, Ramo B, parada, config)
   │
   └─ aprovação humana → só então o veredito é emitido
```

O agente executa no máximo 4 passos por pergunta: buscar, redigir, verificar e comparar. Se os ramos discordam, o agente não redige resposta e marca o caso para revisão humana.

### Para que serve cada arquivo

**Corpus e índice**

| arquivo | papel no workflow |
|---|---|
| `corpus/fide_handbook_E012023.html` | Fonte: as Leis da FIDE em HTML, como baixadas. |
| `corpus/PROVENIENCIA.txt`, `corpus_SHA256.txt` | Origem, data do download e hash, para provar que o corpus não mudou. |
| `src/parse_fide.py` | HTML → `corpus/chunks.jsonl`: uma cláusula por linha, com artigo, artigo-pai e título. Separa o glossário em `glossario.jsonl` (não indexado) e escreve contagens em `relatorio.txt`. |
| `src/buscar_artigo.py` | Constrói e consulta o índice (`indice/`, fora do git). Tem dois backends com a mesma interface, `tfidf` e `e5`. O texto citado é `texto`; o vetor usa `texto_indexado`, que inclui o título do artigo-pai. |
| `src/experimento_recall.py` | Primeiro experimento de busca: 10 consultas em PT e EN → `resultados/recall_tfidf.csv`. Foi o que motivou perguntar só em inglês. |
| `descartados/` | Fonte alternativa avaliada e descartada, com o motivo. |

**Avaliação**

| arquivo | papel no workflow |
|---|---|
| `suite/suite_30.py` | Fonte da suíte: gabarito humano e perguntas em inglês (`PERGUNTAS_EN`). `--verificar` confere os posicionais contra o python-chess; `--emitir` gera o `.jsonl`. |
| `suite/suite_30.jsonl` | A suíte que os outros scripts leem (35 casos, apesar do nome). |
| `src/checar_trechos.py` | Para cada caso: top-k recuperado e se o `artigo_ouro` está entre eles (calculado em código) → `resultados/checagem_trechos_*.csv`. |
| `src/grader.py` | Lê os 105 traces oficiais e aplica os quatro critérios binários (regras no docstring), mede o pass^3 por caso, conta paradas, discordâncias e quem errou, e resume a revisão humana → `resultados/grader_*.{csv,json,md}`. Sem IA. |

**Os dois ramos e o encontro**

| arquivo | papel no workflow |
|---|---|
| `src/legalidade.py` | **Ramo B.** Função pura sobre o python-chess. Não importa nada do Ramo A. FEN ou lance inválido vira veredito `erro`, nunca exceção. |
| `src/montar_prompt.py` | **Ramo A.** Único lugar onde o prompt existe. Só lê pergunta, FEN e lance do caso. Descreve o lance a partir da UCI e da peça na casa de origem, sem `board.san()`, que vazaria a legalidade. `--autoteste` verifica, pela AST, que não há import de `legalidade` e que o prompt fica byte a byte idêntico com o gabarito adulterado. |
| `src/comparador.py` | O único ponto de encontro: função pura que devolve uma das quatro paradas. Nos casos sem lance (afogado, posição morta, 50 lances), usa uma tabela declarada de respostas aceitas. |
| `src/agente.py` | O pipeline: classe → Ramo A (modelo local) → Ramo B → comparador → trace → aprovação. Padrões fixados: modelo, k=5, e5, temperatura 0. Provedores: ollama (padrão), groq, openrouter (chaves no `.env`). |

**Interface e apoio**

| arquivo | papel no workflow |
|---|---|
| `src/interface.py` | Servidor HTTP local, só com a biblioteca padrão. Expõe a suíte, roda o agente, grava aprovações e rótulos. |
| `interface/index.html` | A página: tabuleiro, abas de suíte e testes manuais, chat. JavaScript puro, sem dependências externas. |
| `run.sh` | Atalhos: `corpus`, `indice`, `recall`, `suite`, `interface`, `tudo`. |
| `AGENTS.md` | As regras de comportamento do agente: escopo, citação, recusa, aprovação, o que vai para a nuvem. |
| `CLAUDE.md`, `docs/estado_do_projeto.md` | Invariantes do projeto, decisões tomadas e estado atual. |
| `resultados/` | Todo número do artigo sai de um arquivo daqui. |

### Invariantes que não podem ser quebradas

1. `legalidade.py` não importa nada do Ramo A, e `montar_prompt.py` não importa `legalidade`.
2. O prompt do Ramo A não contém nada derivado da legalidade do lance. Por isso não se usa `board.san()`.
3. `python3 src/montar_prompt.py --autoteste` precisa passar depois de qualquer mudança no prompt.
4. O gabarito é humano: nunca é derivado do python-chess, que só o confere.
5. Depois que as execuções oficiais começarem, não se mexe em prompt, k, modelo nem temperatura.

---

## O que falta

### Execuções e revisão
- [ ] **Aprovação nos traces oficiais:** 103 de 105 estão `pendente` (o grader mostra). Ou se registra a decisão humana em cada um (na interface, pelo menos nos 30 `discordam`) e se roda o grader de novo, ou o artigo declara que a revisão foi por rótulos de caso e que nenhuma resposta oficial foi emitida. Não afirmar "há HITL" sem isso.
- [ ] Revisar os casos sem rótulo de revisão (c21, c23, c28, c29) e decidir os marcados `ajustar`/`remover` (c06, c20, c22, c27, c31) e a premissa do c18. Mudança de gabarito depois das execuções vai declarada no artigo.

### Análise
- [x] **`src/grader.py`:** quatro critérios binários, pass^3 medido, discordâncias e quem errou. A regra de "citação identificável" está no docstring: só vale o número exato de um trecho recuperado (citar o item pai, como `3`, falha). "Sustentada pelo trecho" é medida por um proxy automático (o trecho citado aparece literalmente nos trechos recuperados); a justificativa correta continua sendo julgamento humano.
- [ ] *(se der tempo)* Rodada extra com o `gpt-oss-120b` em nuvem, fora das execuções oficiais, para comparar com o modelo local.

### Relatório (artigo) e apresentação
- [ ] Conferir no Classroom: prazo do artigo, limite de páginas, tamanho do resumo e número de palavras-chave.
- [ ] Escrever o artigo:
  - **Introdução e motivação:** por que um RAG sozinho não basta para regras.
  - **Arquitetura:** os dois ramos, o comparador e a aprovação humana.
  - **Método:** corpus, escolha da busca (tabela TF-IDF × e5), suíte com gabarito humano, configuração fixa.
  - **Resultados:** taxa de discordância, quem errou, pass^3 por critério, erros de busca × erros de leitura.
  - **AI Assurance / limitações:** perguntas só em inglês; o comparador pega **uma** classe de erro; "concordaram" não significa "está certo"; temperatura 0 não garante determinismo; diferenças pequenas (26/30 × 28/30) não são significativas.
  - **Apêndice:** o prompt literal, que prova que o Ramo A não vê o Ramo B.
- [ ] Slides: exportar o PDF como `TE251_2026-2_Exame_<nome_curto>_slides.pdf` e enviar pelo Classroom. Os números dos slides batem com `resultados/grader_resumo.json`.
- [ ] Preparar a demo (e uma captura ou vídeo curto como plano B: cada execução leva 70–110 s em CPU), com um roteiro sugerido:
  1. o c12 (roque com b1 atacada);
  2. um roque ilegal montado no editor;
  3. uma pergunta fora de escopo, que deve ser recusada.
- [ ] *(se der tempo)* Página estática com `chess.svg.board()` por caso, para o artigo.
