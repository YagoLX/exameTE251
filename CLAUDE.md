# TE-251 — Projeto Final (ITA 2026.2)

@AGENTS.md
@docs/estado_do_projeto.md

## O projeto em três linhas

Assistente de regras de xadrez com duas autoridades independentes:
- **Ramo A** (normativo): RAG sobre as Leis do Xadrez da FIDE (`corpus/chunks.jsonl`, 210 cláusulas) + LLM. Responde *qual é a regra*, citando o artigo.
- **Ramo B** (factual): `python-chess` 1.11.2, sem LLM. Responde *o que é legal nesta posição*.

Os ramos **não se veem**. Só se encontram no comparador (código, sem IA), que devolve uma de quatro paradas: `concordam`, `discordam`, `erro`, `recusa`. O resultado é a **taxa de discordância** e **quem estava errado** quando discordaram. O agente não emite veredito a ninguém: a saída de cada execução é o trace, e a revisão humana é feita depois, caso a caso.

## Invariantes: nunca quebrar

1. `src/legalidade.py` não importa nada do Ramo A. `src/montar_prompt.py` não importa `legalidade`.
2. O prompt do Ramo A não pode conter nada derivado da legalidade do lance. **Não usar `board.san()`**: ele gera `O-O-O` e só funciona para lance legal. A descrição do lance sai só da string UCI + a peça na casa de origem.
3. `python3 src/montar_prompt.py --autoteste` precisa passar depois de qualquer mudança no prompt (AST sem import + prompt byte a byte idêntico ao mutar `veredito_ouro`/`artigo_ouro`).
4. `veredito_ouro` e `artigo_ouro` em `suite/suite_30.py` são gabarito **humano**, escrito literal. Nunca derivar do `python-chess`; o script só confere.
5. Glossário (`corpus/glossario.jsonl`) **não** entra no índice: a numeração dele diverge da dos Artigos.
6. `texto` vai na citação; `texto_indexado` (com o título do Artigo-pai) vai só para o vetor.
7. Não inventar métrica. Todo número sai de um arquivo em `resultados/` (o resumo é `resultados/grader_resumo.json`).
8. As 105 execuções oficiais estão feitas: **não mexer no prompt, no k, no modelo, na temperatura nem na suíte**. Achados posteriores sobre o gabarito são declarados, não corrigidos.

## Decisões

- **Perguntas só em inglês.** A busca TF-IDF deu score zero em 9/10 consultas em português (`resultados/recall_tfidf.csv`). Pergunta do prompt = consulta da busca (mesma string).
- **Busca: e5-large, k=5** (22/29 casos com o artigo do gabarito entre os 5 trechos).
- **Modelo do Ramo A: `qwen3:8b` local (Ollama)**, temperatura 0. O `openai/gpt-oss-120b` no Groq saiu do ar em 10/11.
- **Recusa:** a string é `nao consta no material`, sem acento, igual no prompt, na suíte e no grader.
- **3.8.2.2:** os itens `3)` e `4)` são numeração da própria FIDE (conferido no HTML).
- **Classificação da pergunta em código**, não por LLM: se tem FEN, é posicional.
- **Revisão humana posterior**, por rótulos na interface (`resultados/rotulos_humanos.json`): trechos (`suficiente` / `parcial` / `ausente`) e revisão do caso (`ok` / `ajustar` / `remover`, com nota).
- **Avaliação automática:** `src/grader.py`, três critérios binários (citação identificável, trecho ancorado, recusa correta), pass^3 **medido**, discordâncias e quem errou.

## Comandos

```bash
bash run.sh suite                          # confere o gabarito e roda o Ramo B
python3 src/montar_prompt.py --autoteste   # invariantes de independência dos ramos
python3 src/montar_prompt.py c12 --backend e5 -k 5   # imprime o prompt de um caso
python3 src/comparador.py                  # dispara as quatro paradas
python3 src/grader.py                      # avalia os 105 traces oficiais
```

## O que não se pode afirmar

- "o sistema não alucina": o comparador pega **uma classe** de erro.
- "concordaram, logo está certo": busca errada com veredito certo por coincidência passa no comparador (c11, c14 e c16 concordaram sem o artigo do gabarito nos trechos).
- pass^3 calculado como p³ em vez de medido; "temperatura 0 é determinístico".
- "uma pessoa aprovou cada resposta antes de sair": não há aprovação antes da resposta; a revisão humana é posterior.
- Diferenças pequenas entre contagens como se fossem significativas.
