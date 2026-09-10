# Contexto do projeto para agentes de IA

Este arquivo orienta assistentes de IA que trabalham neste repositório.
A **fonte da verdade** sobre requisitos é [`docs/PRD.md`](docs/PRD.md) — consulte-o
antes de propor qualquer mudança de escopo.

## O que é este projeto

Plataforma de predição de atraso de voos sobre os dados abertos do VRA/ANAC,
desenvolvida para a disciplina **PDM_BIA — Processamento de Dados Massivos**
(INF/UFG). São **três entregas encadeadas que compõem um único sistema**, com
apresentação ao vivo em produção:

| Entrega | Data | Escopo |
| --- | --- | --- |
| T1 | 11/09/2026 | Medallion no BigQuery + BigQuery ML (SQL puro) |
| T2 | 23/10/2026 | Pub/Sub + Dataflow → BigQuery; Vertex AI; API no Cloud Run |
| TF | 04/12/2026 | Dataflow chama a API em tempo real, enriquece e persiste; orquestrado com n8n |

## Decisões travadas — não reabrir sem pedido explícito

- **Domínio:** predição de atraso de partida com dados do VRA/ANAC.
- **Fonte (T1, v1.2):** **CSVs mensais** de `siros.anac.gov.br` — um arquivo por
  mês, baixado por script (`baixar_dados.py`), sem WAF. **Não usar os CSVs do
  portal `gov.br`** (domínio diferente do SIROS) — estão atrás de WAF e não são
  baixáveis por script. Schema **instável**: 20 ou 21 colunas conforme o mês
  (coluna extra `Codeshare` a partir de out/2022) e `dt_referencia` em dois
  formatos de data — ver `docs/bronze_silver.md`. Nomes/semântica de campo
  documentados no PRD § 10.2, verificados originalmente contra a API REST
  oficial (`sas.anac.gov.br/sas/vra_api`), que era a fonte da v1.1 e segue
  documentada no PRD § 3.3.1 mas não é usada pela implementação atual — a API
  **trunca respostas sem erro HTTP**, e um download de CSV trunca do mesmo
  jeito: toda ingestão valida contagem e tamanho (RF-001b).
- **Modelo:** classificação binária. Alvo `atrasou = 1` se a partida real exceder
  a prevista em mais de 15 minutos.
- **15 min não é o corte da ANAC.** É o padrão internacional (OTP15). A ANAC
  considera `Pontual` até 30 min. Não "corrigir" o texto para atribuir os 15 min
  à ANAC — isso já esteve errado no PRD e foi corrigido na v1.1.
- **Tipos:** `BOOSTED_TREE_CLASSIFIER` como final, `LOGISTIC_REG` como baseline.
  Escolhidos porque **são exportáveis via `EXPORT MODEL`** e portanto importáveis
  no Vertex AI. Nem todo tipo de modelo BQML exporta — trocar sem verificar
  quebra o T2.
- **Saída:** probabilidade, não a classe.
- **Split temporal:** coluna `is_eval` separa os últimos 60 dias. Split aleatório
  em série temporal está proibido.
- **Payload autocontido:** a API não consulta tabela alguma para montar features.
- **Orquestrador:** n8n no Cloud Run com Cloud SQL Postgres. Composer foi
  descartado por custo (~US$ 300/mês).
- **Monorepo** com tags `v1-medallion`, `v2-streaming`, `v3-final`.

## Em aberto — não tratar como decidido

- **Modelo em cascata (P-08).** Há uma proposta especificada no PRD § 6.5 de
  acrescentar um **segundo modelo** que prevê a *faixa* de duração do atraso
  (`15_30`, `30_60`, `60_120`, `120_mais`, sobre as bordas oficiais da ANAC).
  **Ainda não foi ratificada pelos quatro integrantes.** Até que seja:
  - o escopo contratado é **só o modelo binário**;
  - tudo marcado *(condicional a P-08)* no PRD não deve ser implementado;
  - não escrever `faixa_atraso` na Gold — depois disso a reversão fica cara.

  Não decidir isso sozinho em nenhuma direção. Se a implementação esbarrar no
  tema, perguntar.

## Regras invioláveis

1. **Nenhuma feature pode derivar de horário real, situação do voo,
   justificativa de atraso ou dos campos `ds_situacao_partida` /
   `ds_situacao_chegada`.** Isso é vazamento de alvo e só se manifestaria no
   T2, quando já seria tarde. `ds_situacao_partida` é o caso mais perigoso:
   contém a faixa de atraso pronta, então serve de **rótulo**, jamais de entrada.
2. **`schemas/features.json` é a fonte única da verdade** de features,
   compartilhada pela tabela Gold, pelo `CREATE MODEL`, pelo payload da API e
   pelo `DoFn` do Dataflow. Alterações partem desse arquivo e propagam-se aos
   quatro.
3. **Nunca versionar credenciais, chaves ou identificadores de projeto.** O
   repositório é público. Tudo por variável de ambiente.
4. **Nunca usar `SELECT *`** em query versionada. Toda tabela particionada e
   clusterizada — o BigQuery está no free tier.
5. **Nenhuma etapa da demonstração pode depender de fonte externa.** Os eventos
   vêm do simulador que relê o histórico. A API da ANAC nunca é chamada ao vivo
   durante uma apresentação.
6. **HTTP 200 não é prova de resposta completa.** A API do VRA já devolveu 841 e
   2.768 registros para a mesma chamada, ambas com 200. Toda ingestão valida a
   contagem antes de persistir.

## Convenções

- Documentação e comentários em **português do Brasil**; nomes de variáveis,
  funções, tabelas e colunas em inglês ou no padrão já adotado no arquivo.
- SQL organizado por camada em `sql/<camada>/` (`setup`, `bronze`, `silver`,
  `gold`, `ml`) — sem prefixo numérico de pasta; a ordem de execução é a
  própria ordem das camadas Medallion.
- Não introduzir dependência nova sem justificar.
- Requisitos são referenciados pelo identificador do PRD (`RF-012`, `RNF-008`).

## Prioridade ao decidir

Quando houver conflito entre elegância técnica e confiabilidade da demonstração,
**a demonstração vence**. O peso da avaliação é 60% aplicação prática, 20%
apresentação e 20% código, e estourar o tempo zera o quesito apresentação. Cada
componente novo é superfície de falha adicional em uma janela de 5 minutos.

## Decisões ainda pendentes

Consulte [`docs/PRD.md` § 16](docs/PRD.md#16-decisões-pendentes). Em aberto:
**região GCP** e **recorte do VRA em meses** (bloqueantes), além de **P-08**, o
modelo em cascata. O schema do VRA (P-04) já foi resolvido.
Não assuma valores para as pendentes — pergunte.
