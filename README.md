# ANAC-PDM — Predição de Atraso de Voos

Plataforma de dados e MLOps na Google Cloud que prediz, **antes da decolagem**, a
probabilidade de um voo comercial brasileiro partir com mais de 15 minutos de
atraso. Construída sobre o **VRA (Voo Regular Ativo)** da ANAC — a carga
histórica do T1 usa os **CSVs mensais** publicados em `siros.anac.gov.br`.

> Projeto da disciplina **PDM_BIA — Processamento de Dados Massivos** · INF/UFG · 2026.

---

## Pergunta de negócio

> *Este voo vai atrasar mais de 15 minutos na partida?*

Saída do modelo: **probabilidade**, não a classe. O limiar de 15 minutos é o
padrão internacional de pontualidade (OTP15) — e não o corte da própria ANAC, que
considera pontual todo voo com até 30 minutos de atraso. Na base real, 15 minutos
deixa **18,7%** dos voos na classe positiva; 30 minutos deixaria 9,6%.

Há uma segunda pergunta proposta, ainda **em decisão pelo grupo**: *se atrasar, de
quanto será?* Seria respondida por um segundo modelo em cascata, sobre as faixas
oficiais da ANAC. Ver [P-08](docs/PRD.md#16-decisões-pendentes).

## As três entregas

O projeto é **um único sistema** construído em três incrementos, e não três
trabalhos independentes.

| Entrega | Data | Incremento | Tag |
| --- | --- | --- | --- |
| [Trabalho 1](docs/enunciados/trabalho-1.md) | 11/09/2026 | Arquitetura Medallion no BigQuery + modelo em BigQuery ML (SQL puro) | `v1-medallion` |
| [Trabalho 2](docs/enunciados/trabalho-2.md) | 23/10/2026 | Pub/Sub + Dataflow → BigQuery; modelo no Vertex AI; API REST no Cloud Run | `v2-streaming` |
| [Trabalho Final](docs/enunciados/trabalho-final.md) | 04/12/2026 | Dataflow consulta a API em tempo real, enriquece o evento e persiste; tudo orquestrado com n8n | `v3-final` |

## Arquitetura

```text
CSV VRA/ANAC ─▶ GCS (raw) ──▶ Bronze ──▶ Silver ──┬──▶ Gold agg_*  ──▶ Looker Studio
                                                   └──▶ Gold features ──▶ BigQuery ML
                                                                              │
                                                                     EXPORT MODEL
                                                                              ▼
Simulador ──▶ Pub/Sub ──▶ Dataflow ──▶ Cloud Run API ◀── Vertex AI Endpoint
                              │              │
                              │        (probabilidade)
                              ▼              │
                       BigQuery ◀────────────┘
                       (evento enriquecido)

                     n8n no Cloud Run orquestra o fluxo
```

Diagrama completo em [`docs/PRD.md` § 6](docs/PRD.md#6-visão-da-solução-e-arquitetura).

## Stack

| Camada | Tecnologia |
| --- | --- |
| Fonte | CSVs mensais do VRA (`siros.anac.gov.br`) — um arquivo por mês, sem autenticação. |
| Armazenamento bruto | Google Cloud Storage |
| Data warehouse | BigQuery (Medallion: Bronze / Silver / Gold) |
| Machine learning | BigQuery ML → Vertex AI Model Registry + Endpoint |
| Serviço de predição | FastAPI no Cloud Run |
| Streaming | Pub/Sub + Dataflow (Apache Beam) |
| Orquestração | n8n no Cloud Run, com estado em Cloud SQL Postgres |
| BI | Looker Studio |

## Os dados

| | |
| --- | --- |
| Acesso | `https://siros.anac.gov.br/siros/registros/diversos/vra/<ano>/VRA_<ano>_<mês>.csv` — um arquivo por mês |
| Autenticação | Nenhuma |
| Formato | CSV `;`-separado, encoding Latin-1/CP1252 — **não** UTF-8 |
| Schema | **Instável**: 20 ou 21 colunas conforme o mês (coluna extra `Codeshare` a partir de out/2022) e `dt_referencia` em dois formatos de data. Detalhe em [`docs/bronze_silver.md`](docs/bronze_silver.md) |
| Recorte usado no T1 | 2022-2024 · 36 arquivos · ≈ 856 MB · ≈ 2,8 milhões de linhas |
| Taxa de atraso > 15 min | 18,7% (medido em jun/2026 via API, [PRD § 10.4](docs/PRD.md#104-perfil-verificado-da-base)) |

Ressalvas que moldaram o projeto:

- **Os CSVs do portal `gov.br` não são baixáveis por script.** Esse portal está
  atrás de um WAF que devolve um desafio JavaScript no lugar do arquivo.
  `siros.anac.gov.br` — de onde o T1 efetivamente baixa os dados — é um domínio
  diferente, sem esse bloqueio: um `GET` simples por mês basta
  (`baixar_dados.py`).
- **O schema do CSV não é fixo.** Ao inspecionar os 36 arquivos do recorte
  2022-2024, 15 trazem uma 21ª coluna (`Codeshare`) e 21 trazem só 20; a coluna
  `dt_referencia` aparece em dois formatos de data diferentes conforme o mês.
  Tratado na Bronze (`allow_jagged_rows`) e na Silver (parse com fallback).
- **Nem HTTP 200 nem upload "concluído" são prova de dado completo.** A API do
  SAS/ANAC (fonte planejada originalmente) já devolveu 841 e depois 2.768
  registros para a mesma chamada, ambas com HTTP 200 — achado que motivou a
  regra geral do projeto: **toda ingestão valida contagem antes de persistir**.
  Para o CSV, a validação real é comparar tamanho e contagem de linhas do
  arquivo local contra o que chegou no GCS
  (`scripts/ingest_bronze_vra_to_gcs.py`).

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [`docs/PRD.md`](docs/PRD.md) | Documento de requisitos: escopo, requisitos funcionais e não funcionais, métricas-alvo, modelo de dados, glossário, riscos, cronograma e critérios de aceite |
| [`docs/enunciados/`](docs/enunciados/) | Transcrição fiel dos três enunciados da disciplina |

## Estado atual (T1)

Implementado e versionado neste repositório:

| Etapa | Onde |
| --- | --- |
| Download dos CSVs mensais do VRA | [`scripts/baixar_dados.py`](scripts/baixar_dados.py) → `vra/*.csv` (não versionado, 5,3 GB) |
| Upload para o GCS com validação de contagem/tamanho | [`scripts/ingest_bronze_vra_to_gcs.py`](scripts/ingest_bronze_vra_to_gcs.py) |
| Setup do dataset BigQuery | [`sql/setup/create_dataset.sql`](sql/setup/create_dataset.sql) |
| Criação da Bronze (`external table`) | [`notebooks/raw_to_bronze_vra.ipynb`](notebooks/raw_to_bronze_vra.ipynb) · DDL equivalente em [`sql/bronze/`](sql/bronze/) |
| Criação da Silver (tipagem, dedup, filtros) | [`notebooks/bronze_to_silver_vra.ipynb`](notebooks/bronze_to_silver_vra.ipynb) · SQL em [`sql/silver/`](sql/silver/) |
| Gerenciamento de dependências Python | [`pyproject.toml`](pyproject.toml) / `uv.lock` — `uv run python <script>` |


## Estrutura planejada do repositório

```text
terraform/                  # infraestrutura declarada, mínima
scripts/                    # ingestão batch: baixa CSV, valida, grava no GCS [implementado]
notebooks/                  # notebooks de criação das tabelas por camada [implementado]
streaming/
  producer/                 # simulador de eventos → Pub/Sub
  dataflow/                 # pipeline Beam
sql/
  setup/  bronze/  silver/  gold/  ml/   # setup/bronze/silver implementados
api/                        # FastAPI + Dockerfile (Cloud Run)
orchestration/              # workflows n8n
schemas/features.json       # contrato de features
docs/
```

`sql/` tem uma pasta por camada Medallion (sem prefixo numérico) — a ordem de
execução é a própria ordem das camadas: `bronze` → `silver` →
`gold` → `ml`.

## Restrições que moldam o projeto

- **Custo.** Crédito educacional de US 200, fragmentado em quatro billing
  accounts de US 50. Recursos que cobram por hora ligada (Vertex AI Endpoint,
  Dataflow streaming) são criados dias antes da apresentação e desligados logo
  depois.
- **Demonstração ao vivo.** Cada entrega precisa estar rodando em produção no dia
  da apresentação, com tempo cronometrado — estourar o limite zera o quesito.
  Nenhuma etapa da demo depende de fonte externa: os eventos vêm de um simulador
  que relê o histórico.
- **Sem vazamento de alvo.** Só entram no modelo atributos conhecidos antes da
  decolagem. Horário real, situação do voo, justificativa de atraso e os campos
  `ds_situacao_partida` / `ds_situacao_chegada` estão explicitamente proibidos como
  feature. O último é o mais tentador: já contém a faixa de atraso pronta, e por
  isso serve como rótulo, nunca como entrada.

## Equipe

- Igor Reis Braziel
- João Henrique F. Simielli
- Bruno Moreira Lavalli Calura
- João Pedro de Castro Gomes Fernandes

## Segurança

Nenhuma credencial, chave de serviço ou identificador de projeto é versionado.
Todos os identificadores são parametrizados por variável de ambiente.
