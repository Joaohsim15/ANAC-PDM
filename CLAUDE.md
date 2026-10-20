# Contexto do projeto para agentes de IA

Este arquivo orienta assistentes de IA que trabalham neste repositório.
A **fonte da verdade** sobre requisitos é [`docs/PRD.md`](docs/PRD.md) — consulte-o
antes de propor qualquer mudança de escopo.

## O que é este projeto

Plataforma de predição de atraso de voos sobre os dados abertos do VRA/ANAC,
desenvolvida para a disciplina **PDM_BIA — Processamento de Dados Massivos**
(INF/UFG). São **três entregas encadeadas que compõem um único sistema**, com
apresentação ao vivo em produção:

| Entrega | Data | Escopo | Situação |
| --- | --- | --- | --- |
| T1 | 11/09/2026 | Medallion no BigQuery + BigQuery ML (SQL puro) | ✅ entregue — tag `v1-medallion` |
| T2 | 23/10/2026 | Pub/Sub + Dataflow → BigQuery; Vertex AI; API no Cloud Run | 🟡 em andamento — ver "Estado atual" |
| TF | 04/12/2026 | Dataflow chama a API em tempo real, enriquece e persiste; orquestrado com n8n | ⚪ não iniciado |

## Estado atual (09/10/2026)

**Dados (T1).** A Gold `tb_anac_gold_features_atraso` cobre **2016-01-01 a
2024-12-31: 6.187.534 voos**, com 17,4% de atraso > 15 min. O GCS tem 120 CSVs
(2016–2025) em quatro lotes. O lote `vra_2025_2025` foi ingerido no GCS, mas
**não está na Silver nem na Gold**: está retido fora do treino. A
documentação mais antiga (README, PRD, `docs/bronze_silver.md`, slides do T1)
ainda fala em recorte 2022-2024 e ganho de 0,0167; os números abaixo são os
medidos.

**M1 — promovido com clima em 18/10/2026.** O M1 de produção
(`mdl_anac_m1_boosted_tree`) foi retreinado com as 10 features originais +
as 9 de meteorologia (ver seção de METAR abaixo), sobre
`tf_anac.vw_anac_gold_treino_m1_clima` (tabela
`tf_anac.tb_anac_gold_features_atraso_clima`, separada da Gold de voo
original). Avaliação nos últimos 60 dias (151.469 voos,
`vw_anac_gold_avaliacao_m1_clima`): **AUC 0,6539** contra 0,6516 do baseline
(ganho de 0,0022 sobre o baseline — nenhum dos dois atinge os alvos de
0,70/0,02 do PRD, mas isso já era o caso antes do clima, não é regressão). A
validação lado a lado antes de promover (mesmo split, M1 sem clima vs com
clima) deu ganho de +0,0005 de AUC geral e +0,0013 restrito aos voos com
clima preenchido (89,6% da avaliação) — marginal, mas o grupo decidiu
promover mesmo assim. `ML.GLOBAL_EXPLAIN` mostra sinal real em
`clima_fenomenos` (6ª feature mais importante, acima de
`duracao_prevista_min`, `sg_equipamento_icao`, `dia_semana`); as demais 8
features de clima contribuem pouco. `sql/ml/model_m1_boosted_tree_clima.sql`
e `ml_evaluate_clima.sql` (modelo e avaliação de validação) foram removidos
depois da promoção — a produção já carrega o conteúdo deles.

**T2 — pronto e verificado no GCP:**
- `schemas/features.json` (v2, 19 features: 10 originais + 9 de clima
  nullable) é a fonte única, propagada à Gold-clima, ao `CREATE MODEL`, à API
  e ao Dataflow.
- `api/` (FastAPI): serviço Cloud Run `anac-api` publicado em 09/10, privado e
  com `min-instances=0`. Testado ponta a ponta em 09/10, **antes da promoção
  do M1 com clima** (paridade com o `ML.PREDICT` 0,6077, 422 para payload
  inválido, 403 sem token, p95 de 359 ms) — reensaiar com o modelo novo e o
  payload com os 9 campos de clima antes da apresentação.
- **`/explain` e log de predições — diferencial, adicionado em 19/10/2026.**
  `POST /explain` (mesmo payload do `/predict`) devolve, além da
  probabilidade, a contribuição de cada feature para aquela previsão
  específica (`ML.EXPLAIN_PREDICT`, direto no BigQuery — não é o Vertex, por
  isso é mais lento e fica num endpoint separado do caminho crítico medido
  em `/predict`). `/predict` passou a gravar (via `BackgroundTask`, sem
  afetar a latência nem a resposta) toda predição em
  `tf_anac.tb_anac_predicoes_log`; se o chamador informar `nr_voo`,
  `dt_referencia` e `dt_partida_prevista` como query params (não são
  features, só chave de reconciliação — o payload do `/predict` continua
  autocontido), `sql/ml/reconciliar_predicoes.sql` compara depois a previsão
  com o resultado real na Gold e mede acurácia **em produção**, não só na
  avaliação offline. Testado de ponta a ponta contra o modelo e os dados
  reais (voo GLO 9609 de 20/12/2024: previu sem atraso, resultado real foi
  sem atraso, reconciliação bateu). Bug real encontrado e corrigido:
  `ML.EXPLAIN_PREDICT` exige `top_k_features` como literal constante no
  `STRUCT(...)`, não aceita parâmetro de query.
- `streaming/producer` (simulador) e `streaming/dataflow` (Beam): rodou no
  Dataflow com 30/30 eventos gravados e lag médio de 3 s; job drenado.
- `terraform/`: 14 recursos aplicados. State no bucket `<projeto>-anac-tfstate`.
- O M1 está registrado no Vertex Model Registry como `anac_m1_boosted_tree`.
- O endpoint `anac-atraso-endpoint` foi testado com o M1 implantado em 09/10
  (deploy de 33 min) e está de novo **sem modelo implantado**. Religar em 21/10.

**T2 — falta:** reimplantar o modelo em 21/10 e publicar a API com `--demo`,
ativar as service accounts dedicadas (exige o Owner do projeto) e ensaiar a
demo. Como operar: [`docs/t2-operacao.md`](docs/t2-operacao.md).

**Meteorologia (IEM ASOS/METAR) — decidido em 15/10/2026, fonte trocada no
mesmo dia.** O grupo decidiu enriquecer o modelo com observações
meteorológicas. Isso **substitui** o streaming de voos no T2: voos continuam
em **batch** (Medallion do T1, inalterado); meteorologia passa a ser a
ingestão em **streaming** que cumpre o requisito do T2. O retreino do M1 com
clima **está em escopo do T2**, não do TF — risco de cronograma (8 dias até
23/10) sinalizado e aceito. A fonte escolhida é a **Iowa Environmental
Mesonet (IEM)**, rede `BR__ASOS` (`mesonet.agron.iastate.edu`) — **não** a
API-REDEMET/DECEA, cogitada primeiro mas abandonada porque o cadastro
exigido não foi concluído; a IEM não exige cadastro nem chave. Detalhe em
[`docs/PRD.md` §3.3.2](docs/PRD.md#332-fonte-de-dados-de-meteorologia-iem-asosmetar)
e plano de implementação em `/Users/joaopedro/.claude/plans/nifty-rolling-blossom.md`.
**P-09 resolvida em 15/10/2026, com dados reais do projeto:**
- **Fuso do VRA:** `dt_partida_prevista`/`dt_partida_real` estão em **horário
  de Brasília (UTC-3) para todos os aeródromos**, não hora local de cada um —
  confirmado comparando `duracao_prevista_min` de rotas entre fusos
  diferentes (SBGR↔SBRB, SBPA→SBEG) contra a duração real de voo conhecida;
  se fosse hora local por aeródromo, a duração apareceria sistematicamente
  menor pela diferença de fuso, o que não ocorre. Conversão para UTC (preciso
  para casar com a IEM) é **`DATETIME_ADD(dt_partida_prevista, INTERVAL 3
  HOUR)`, fixo** — não precisa do fuso IANA por estação que a IEM fornece.
  Ressalva conhecida e não tratada: o Brasil teve horário de verão (UTC-2 em
  parte do ano) até fevereiro/2019, então essa conversão fixa tem um erro de
  ~1h em datas de verão anteriores a 2019 — aceito como aproximação.
- **Cobertura real:** a Gold de produção tem **100 ICAO de origem
  distintos** (não 175 — esse número do PRD §10.4 vem de uma amostra
  diferente, da API, não da Gold final). Das 100, **65 têm estação na rede
  `BR__ASOS`** da IEM, cobrindo **92,9% do volume de voos**. As 35 sem
  estação são majoritariamente aeroportos **internacionais** (SAEZ, SCEL,
  KMIA, LPPT, SABE, MPTO, SKBO, SPJC, SUMU, LEMD, EDDF, LFPG, EHAM, SGAS,
  entre outros) — fora da rede `BR__ASOS` por definição; ficam com a feature
  de clima nula. Não perseguir essa cobertura internacional por ora (dado o
  prazo do T2) — ganho marginal de 7% do volume contra o custo de mapear a
  rede ASOS certa em ~10 países diferentes.
- **Join Gold+clima por desigualdade de tempo não escala.** A primeira versão
  de `sql/gold/gold_features_atraso_clima.sql` casava voo e METAR só por
  `sg_icao_origem = sg_icao` + `dt_observacao_utc` dentro da janela de 3h — o
  BigQuery não tratou isso como hash join e o job ficou **mais de 3h RUNNING**
  (cancelado em 18/10/2026, 0 bytes faturados). Reescrito para casar por
  **igualdade de (aeródromo, hora truncada)** — a janela de 3h cabe em no
  máximo 4 horas truncadas, geradas por voo via `UNNEST`, com as condições de
  desigualdade originais mantidas no `ON` só para a correção final. Resultado:
  **53 segundos** para os 9 anos completos (6.187.534 voos, confere exato com
  a Gold de produção; **90,2% ficou com clima preenchido**, perto do estimado
  por volume). Mesma armadilha vale para qualquer join tipo ASOF futuro no
  BigQuery — preferir igualdade com bucket de tempo a desigualdade pura.

Streaming de voos (Pub/Sub `anac-voos` → Dataflow → `tb_anac_stream_eventos`,
já testado em 09/10) será desativado e substituído pelo equivalente de
METAR; não reativar o de voos sem decisão do grupo.

## Ambiente GCP — leia antes de mexer

- **O projeto é compartilhado com exercícios de aula.** Os recursos do trabalho
  usam o prefixo `anac-` (Pub/Sub, Artifact Registry, buckets), o dataset
  `tf_anac`, o bucket `dados-anac-vra` e os modelos `mdl_anac_*`. **Não usar,
  alterar nem apagar** nada de aula:
  - Pub/Sub `aula-pdm-*`;
  - datasets `aula_pdm`, `anuncios`, `erp`;
  - os buckets de MLOps e de anúncios das aulas;
  - o modelo Vertex `rf-preco-imoveis`;
  - `tf_anac.tb_anac_silver_pubsub`, que é resto de aula dentro do dataset do
    trabalho.

  O Pub/Sub `aula-pdm-anac` **não serve ao T2**: grava direto no BigQuery, sem
  Dataflow. Antes de reaproveitar qualquer recurso existente, confira a origem.
- **Recursos cobrados por hora** ficam fora do Terraform e são ligados e
  desligados por `scripts/t2/`: o modelo no endpoint do Vertex, o job Dataflow e
  o Cloud Run com `min-instances=1`. Ao terminar uma sessão, nada disso pode
  ficar ligado. Implantar modelo no endpoint é ação cobrada: confirme com o
  usuário antes.
- **O papel do usuário é Editor**, que não concede IAM. Service accounts
  dedicadas só com `manage_iam = true` no Terraform, aplicado pelo Owner. O
  dead-letter é feito no próprio pipeline pelo mesmo motivo: a política nativa
  do Pub/Sub exigiria conceder papéis.
- **Sirva o modelo pelo registro direto BQML → Vertex** (`ALTER MODEL ... SET
  OPTIONS (vertex_ai_model_id = ...)`), não pelo artefato em
  `gs://dados-anac-vra/models/`. O artefato foi exportado em 10/09, antes do
  treino final de 11/09, e diverge do modelo vigente (0,634 contra 0,608 no voo
  de exemplo).
- **Credenciais ADC podem apontar a cota para outro projeto.** Os scripts fixam
  `GOOGLE_CLOUD_QUOTA_PROJECT`; ao rodar bibliotecas Python à mão, faça o mesmo.
  O token do `gcloud` expira com frequência: `gcloud auth login --update-adc`.

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
  Escolhidos porque **chegam ao Vertex AI** (exportáveis via `EXPORT MODEL` e
  registráveis direto no Model Registry). Nem todo tipo de modelo BQML é servível
  no Vertex — trocar sem verificar quebra o T2.
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
  - **a coluna `faixa_atraso` já existe na Gold** (foi escrita no T1). Não a
    use em nenhum modelo, API ou pipeline, e não a remova sem decisão do grupo:
    se a cascata for descartada, a coluna sai.

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
3. **Nunca versionar credenciais, chaves de serviço ou tokens.** O repositório
   é público; segredos ficam em variável de ambiente. O id do projeto GCP **pode**
   aparecer em código e documentação (liberado em 07/10/2026) — não o trate como
   segredo nem proponha removê-lo.
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
  `gold`, `ml`, `streaming`) — sem prefixo numérico de pasta; a ordem de
  execução é a própria ordem das camadas Medallion. SQL novo usa
  `${PROJECT_ID}` no lugar do id do projeto (substituído por `envsubst` nos
  scripts).
- Não introduzir dependência nova sem justificar.
- **Código, SQL, notebooks e material gerado não citam o PRD** nem seus
  identificadores (`RF-012`, `RNF-008`, `P-08`, seções). Cada artefato explica o
  próprio porquê. As citações acima, neste arquivo, servem só para orientar o
  agente.
- Configuração local fica em `.env` e `terraform/terraform.tfvars`, ambos fora
  do Git; os modelos versionados são `.env.example` e
  `terraform/terraform.tfvars.example`.

## Prioridade ao decidir

Quando houver conflito entre elegância técnica e confiabilidade da demonstração,
**a demonstração vence**. O peso da avaliação é 60% aplicação prática, 20%
apresentação e 20% código, e estourar o tempo zera o quesito apresentação. Cada
componente novo é superfície de falha adicional em uma janela de 5 minutos.

## Decisões ainda pendentes

Consulte [`docs/PRD.md` § 16](docs/PRD.md#16-decisões-pendentes). O schema do
VRA (P-04) já foi resolvido. Situação das demais:

| Decisão | Situação |
| --- | --- |
| **Região GCP** | **Adotada na prática: `us-central1`.** Vertex, Dataflow, Cloud Run, Artifact Registry e Terraform já estão lá, e o dataset está em `US`. Falta registrar formalmente no PRD |
| **Recorte do VRA em meses** | **Adotado na prática:** 2016–2024 na Gold; 2025 ingerido no GCS e retido fora da Silver. Falta o grupo ratificar e registrar |
| **P-08 — cascata** | Em aberto (ver acima) |
| ~~**P-09**~~ | ~~Meteorologia: fuso e cobertura~~ | ✅ **RESOLVIDA em 15/10/2026.** Fuso é horário de Brasília fixo (UTC-3), não local por aeródromo; cobertura real é 65/100 ICAO de origem da Gold, 92,9% do volume de voos. Ver `docs/PRD.md` §3.3.2 |
| Quem apresenta o T2 · rotação das contas de faturamento | Em aberto |

Não assuma valores para as pendentes nem trate as "adotadas na prática" como
ratificadas — pergunte.
