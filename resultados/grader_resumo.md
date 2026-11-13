# Resumo do grader (105 execucoes oficiais, 35 casos)

Gerado por `python3 src/grader.py` a partir de `traces/c*_r*.json`. Regras dos criterios no docstring do script.

- Configuracoes distintas: 1 (qwen3:8b, temperatura 0.0, k=5, e5); modelo servido: {'qwen3:8b': 105}
- Casos com o mesmo prompt (sha256) nas 3 repeticoes: 35/35

## Criterios

| criterio | execucoes que passam | pass^3 (casos) | casos que falham em alguma |
|---|---|---|---|
| citacao_identificavel | 72/81 | 24/27 | c04, c12, c17 |
| trecho_ancorado | 81/81 | 27/27 | - |
| recusa_correta | 96/105 | 32/35 | c22, c24, c29 |
| revisao_registrada | 2/105 | 0/35 | c01, c02, c03, c04, c05, c06, c07, c08, c09, c10, c11, c12, c13, c14, c15, c16, c17, c18, c19, c20, c21, c22, c23, c24, c25, c26, c27, c28, c29, c30, c31, c32, c33, c34, c35 |
| veredito_a_correto | 39/72 | 13/24 | c01, c04, c06, c09, c12, c15, c17, c21, c22, c23, c24 |
| veredito_b_correto | 72/72 | 24/24 | - |

## Paradas

- Todas: {'discordam': 30, 'concordam': 39, 'recusa': 24, 'sem_verificacao': 12}
- Por classe: {'posicional:discordam': 30, 'posicional:concordam': 39, 'posicional:recusa': 3, 'normativa:sem_verificacao': 12, 'normativa:recusa': 21}
- Parada igual a esperada: {'diferente': 33, 'igual': 72}; casos diferentes: c01, c04, c06, c09, c15, c17, c21, c22, c23, c24, c29

## Discordancia entre os ramos (posicionais)

- 72 execucoes em 24 casos
- Discordam: 30 execucoes, casos c01, c04, c06, c09, c12, c15, c17, c21, c23, c24
- Quem errou nas discordancias: {'so_A_errou': 30}
- Concordam: 39 execucoes, casos c02, c03, c05, c07, c08, c10, c11, c13, c14, c16, c18, c19, c20
- Concordam sem o artigo do gabarito nos trechos: c11, c14, c16
- Concordam com citacao nao identificavel: -

## Estabilidade

- Casos que variaram entre as 3 repeticoes: 2 (c02: ['ilegal|3.7.3.1', 'ilegal|3.7.3.2']; c16: ['ilegal|4.4.1', 'ilegal|4.4.3'])

## Busca

- Artigo do gabarito entre os 5 trechos: 22/29 casos

## Revisao humana

- Aprovacao nas execucoes oficiais: {'pendente': 103, 'rejeitado': 2}
- Interface (exploratoria, fora da contagem oficial): {'openai/gpt-oss-120b:aprovado': 4, 'qwen3:8b:pendente': 7, 'openai/gpt-oss-120b:rejeitado': 2, 'qwen3:8b:aprovado': 6, 'openai/gpt-oss-120b:revisao_humana': 1, 'openai/gpt-oss-120b:pendente': 4, 'qwen3:8b:rejeitado': 22, 'qwen3:8b:revisao_humana': 4}
- Rotulos por caso: 35 casos; trechos {'suficiente': 15, 'ausente': 12, 'parcial': 8}; revisao {'ok': 26, 'ajustar': 4, 'sem_rotulo': 4, 'remover': 1}
- Casos marcados para ajustar ou remover: c06, c20, c22, c27, c31
- Casos sem revisao: c21, c23, c28, c29
- Traces oficiais com rotulo de resposta correta: c34_r1.json, c35_r1.json
