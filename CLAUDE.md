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

## Estado atual (07/10/2026)

**Dados (T1).** A Gold `tb_anac_gold_features_atraso` cobre **2016-01-01 a
2024-12-31: 6.187.534 voos**, com 17,4% de atraso > 15 min. O GCS tem 120 CSVs
(2016–2025) em quatro lotes. O lote `vra_2025_2025` foi ingerido no GCS, mas
**não está na Silver nem na Gold**: está retido fora do treino. Avaliação nos
últimos 60 dias (151.469 voos): M1 AUC **0,6527** contra 0,6434 do baseline. A
documentação mais antiga (README, PRD, `docs/bronze_silver.md`, slides do T1)
ainda fala em recorte 2022-2024 e ganho de 0,0167; os números acima são os
medidos.

**T2 — pronto e verificado no GCP:**
- `schemas/features.json` existe e aceita 99,97% da Gold real.
- `api/` (FastAPI): imagem publicada no Artifact Registry; o serviço Cloud Run
  **ainda não foi publicado**.
- `streaming/producer` (simulador) e `streaming/dataflow` (Beam): rodou no
  Dataflow com 30/30 eventos gravados e lag médio de 3 s; job drenado.
- `terraform/`: 14 recursos aplicados. State no bucket `<projeto>-anac-tfstate`.
- O M1 está registrado no Vertex Model Registry como `anac_m1_boosted_tree`.
- O endpoint `anac-atraso-endpoint` existe **sem modelo implantado**.

**T2 — falta:** implantar o modelo no endpoint, publicar a API, medir o p95,
ativar as service accounts dedicadas (exige o Owner do projeto) e ensaiar a
demo. Como operar: [`docs/t2-operacao.md`](docs/t2-operacao.md).

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
| Quem apresenta o T2 · rotação das contas de faturamento | Em aberto |

Não assuma valores para as pendentes nem trate as "adotadas na prática" como
ratificadas — pergunte.
