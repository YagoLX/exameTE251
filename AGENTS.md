# AGENTS.md

Escopo: Leis do Xadrez da FIDE, edicao em vigor desde 01/01/2023, indexada em corpus/. Fora disso, recuse.
Toda afirmacao normativa cita Artigo de trecho recuperado nesta execucao; sem trecho, responda exatamente "nao consta no material".
Veredito de legalidade vem de legalidade(fen, lance), nunca do texto do modelo, mesmo quando o artigo parece claro.
O Ramo A (corpus) nunca recebe a saida do Ramo B (ferramenta). Os dois so se encontram no comparador.
Ferramentas: buscar_artigo e legalidade. Sao leitura e funcao pura, sem efeito fora do processo.
Nao emita veredito a ninguem: a saida de cada execucao e o trace. A revisao humana e feita depois, caso a caso.
Se os dois ramos discordarem, a parada "discordam" fica no trace, que vai para a revisao humana.
Limite de 4 passos por pergunta. Resposta do modelo sem JSON, FEN invalido ou lance imparsavel viram estado de erro, nao frase.
Nunca declare partida encerrada, resultado homologado, penalidade aplicada ou posicao "conforme as regras".
Ao modelo (local ou em nuvem) vao a pergunta, a posicao, o lance e os trechos do corpus publico, e nada mais.
