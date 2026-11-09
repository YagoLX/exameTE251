# TE-251 — Projeto Final (ITA 2026.2)

@AGENTS.md
@docs/estado_do_projeto.md

## O projeto em três linhas

Assistente de regras de xadrez com duas autoridades independentes:
- **Ramo A** (normativo): RAG sobre as Leis do Xadrez da FIDE (`corpus/chunks.jsonl`, 210 cláusulas) + LLM. Responde *qual é a regra*, citando o artigo.
- **Ramo B** (factual): `python-chess` 1.11.2, sem LLM. Responde *o que é legal nesta posição*.

Os ramos **não se veem**. Só se encontram no comparador (código, sem IA), que devolve uma de quatro paradas: `concordam`, `discordam`, `erro`, `recusa`. O resultado do artigo é a **taxa de discordância** e **quem estava errado** quando discordaram.

## Prazo

Apresentação na **sexta, 13/11/2026**. São 4 dias a partir de 09/11. Priorizar o que vira evidência no artigo e na demo; cortar o resto.

## Invariantes: nunca quebrar

1. `src/legalidade.py` não importa nada do Ramo A. `src/montar_prompt.py` não importa `legalidade`.
2. O prompt do Ramo A não pode conter nada derivado da legalidade do lance. **Não usar `board.san()`**: ele gera `O-O-O` e só funciona para lance legal. A descrição do lance sai só da string UCI + a peça na casa de origem.
3. `python3 src/montar_prompt.py --autoteste` precisa passar depois de qualquer mudança no prompt (AST sem import + prompt byte a byte idêntico ao mutar `veredito_ouro`/`artigo_ouro`).
4. `veredito_ouro` e `artigo_ouro` em `suite/suite_30.py` são gabarito **humano**, escrito literal. Nunca derivar do `python-chess`; o script só confere.
5. Glossário (`corpus/glossario.jsonl`) **não** entra no índice: a numeração dele diverge da dos Artigos.
6. `texto` vai na citação; `texto_indexado` (com o título do Artigo-pai) vai só para o vetor.
7. Não inventar métrica. Todo número do artigo sai de um arquivo em `resultados/`.
8. Depois que as 90 execuções começarem, **não mexer no prompt, no k, no modelo nem na temperatura**.

## Decisões de 09/11

- **Perguntas só em inglês.** A busca TF-IDF deu score zero em 9/10 consultas em português (`resultados/recall_tfidf.csv`). Pergunta do prompt = consulta da busca (mesma string); `--consulta` deixa de ser necessário. Vira limitação declarada no AI Assurance.
- **`e5` fora do caminho crítico.** Só entra se rodar sem custo de tempo.
- **Sonda manual no Groq cancelada.** No lugar dela: checagem humana dos trechos recuperados, caso a caso, com rótulo `suficiente` / `parcial` / `ausente`.
- **c12 checado:** a 3.8.2.2 vem em 2º no top-3 → `suficiente`. Se o modelo errar o c12, o erro é de leitura, não de busca.
- **Classificação da pergunta em código**, não por LLM: se tem FEN, é posicional.

## A conferir antes de rodar qualquer coisa

- [ ] Na 3.8.2.2, o chunk mostra os itens como "3)" e "4)". Conferir no HTML se a FIDE numera assim; se não, corrigir `parse_fide.py` (citação com número que não é da FIDE).
- [ ] String de recusa: o prompt usa `nao consta no material` e o doc de design usa `não consta no material`. Escolher uma e usar igual no prompt, na suíte e no grader.
- [ ] Modelo do Ramo A e id exato: **ainda não decidido**.
- [ ] Classroom: prazo do artigo, limite de páginas, tamanho do resumo, nº de palavras-chave.

## Tarefas, em ordem

Hoje (antes de qualquer execução):
1. `git init` + primeiro commit (`.gitignore` já exclui `.venv/` e `indice/`).
2. Itens da seção "A conferir".
3. Suíte em inglês: reescrever as perguntas como um jogador perguntaria, sem copiar o vocabulário da FIDE. Fixar antes de rodar a busca; não reescrever depois de ver falhar. Decidir se entram c31–c35 (fora de escopo, `parada_esperada: recusa`).
4. Prompt final: tabuleiro em ASCII (`print(board)`), lance descrito em palavras, **trechos antes das instruções**, instruções mais curtas. Rodar o autoteste.

Depois:

5. Checagem de trechos nos 30 casos → CSV em `resultados/` com caso, consulta, top-3 (artigo + texto), "`artigo_ouro` no top-3?" (código) e rótulo humano vazio.
6. `src/comparador.py`: função pura, ~30 linhas, sem IA. Pronto quando as quatro paradas disparam sob demanda.
7. `src/agente.py` (pipeline): pergunta → classe (código) → Ramo A via API + Ramo B → comparador → trace JSON em `traces/` → aprovação humana (mínimo: `input()` s/n gravado no trace).
8. 30 × 3 execuções com tudo fixo.
9. `src/grader.py`: quatro critérios binários (sustentado, citação identificável, recusa, revisão antes da ação), pass^3 **medido** por tarefa e critério, quatro contagens separadas. Mais o par: (a) discordâncias nas 24 posicionais; (b) quem errou quando discordaram.
10. Se der tempo: `src/render.py`, página HTML estática com `chess.svg.board()` por caso. No c12, b1 em vermelho, d1/c1 em verde.

## Comandos

```bash
cd ~/Estudos/exameTE251 && source .venv/bin/activate
bash run.sh tudo           # parser + índice + recall
bash run.sh suite          # confere gabarito e roda o Ramo B
python3 src/montar_prompt.py --autoteste
python3 src/montar_prompt.py c12 --consulta "may white castle queenside if b1 is attacked"
```

Pendência conhecida: `src/experimento_recall.py` não tem `--modelo` (só atrapalha com `e5`).

## O que o artigo NÃO pode afirmar

- "o sistema não alucina": o comparador pega **uma classe** de erro.
- "concordaram, logo está certo": busca errada com veredito certo por coincidência passa no comparador.
- pass^3 calculado como p³ em vez de medido; "temperatura 0 é determinístico".
- "há HITL" sem aprovação gravada nos traces.
- Diferenças entre 26/30 e 28/30 como se fossem significativas.
