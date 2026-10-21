# ANAC-PDM — Predição de Atraso de Voos

Plataforma de dados e MLOps na Google Cloud que prediz, **antes da decolagem**, a
probabilidade de um voo comercial brasileiro partir com mais de 15 minutos de
atraso. Usa o histórico de voos do **VRA (Voo Regular Ativo)** da ANAC e
observações meteorológicas **METAR** dos aeroportos.

> Projeto da disciplina **PDM_BIA — Processamento de Dados Massivos** · INF/UFG · 2026.

| | |
| --- | --- |
| Apresentação do T2 | <https://joaohsim15.github.io/ANAC-PDM/docs/apresentacao/t2-apresentacao.html> |
| API no Cloud Run | <https://anac-api-67210160247.us-central1.run.app> — **privada**, ver [Chamar a API](#chamar-a-api) |
| Versão entregue no T2 | tag [`v2-streaming`](https://github.com/Joaohsim15/ANAC-PDM/tree/v2-streaming) |

---

## Pergunta de negócio

> *Este voo vai atrasar mais de 15 minutos na partida?*

Saída do modelo: **probabilidade**, não a classe. O limiar de 15 minutos é o
padrão internacional de pontualidade (OTP15), e não o corte da própria ANAC, que
considera pontual todo voo com até 30 minutos de atraso.

## As três entregas

O projeto é **um único sistema** construído em três incrementos.

| Entrega | Data | Incremento | Tag |
| --- | --- | --- | --- |
| [Trabalho 1](docs/enunciados/trabalho-1.md) | 11/09/2026 | Arquitetura Medallion no BigQuery + modelo em BigQuery ML | `v1-medallion` |
| [Trabalho 2](docs/enunciados/trabalho-2.md) | 23/10/2026 | Arquitetura híbrida: METAR em streaming (Pub/Sub + Dataflow); modelo no Vertex AI; API REST no Cloud Run | `v2-streaming` |
| [Trabalho Final](docs/enunciados/trabalho-final.md) | 04/12/2026 | Dataflow chama a API em tempo real e enriquece o evento; orquestração | `v3-final` |

## Arquitetura (T2)

Dois pipelines que se encontram no modelo:

```text
BATCH · histórico 2016–2024 (muda uma vez por mês)

  CSV VRA + METAR ─▶ Cloud Storage ─▶ Bronze ─▶ Silver ─▶ Gold ─▶ BigQuery ML ─▶ Vertex AI
                     (por lote)       (external) (tipada) (features   (treino)     Model Registry
                                                           + clima)                 + Endpoint
                                                                                        ▲
STREAMING · tempo real (uma observação por hora por aeroporto)                         │
                                                                                        │
  Gerador METAR ─▶ Pub/Sub ─▶ Dataflow ─▶ BigQuery: tb_anac_stream_metar               │
                  anac-metar  (valida)    (mesmo dataset da Silver de METAR)            │
                                 │                                                      │
                                 └─▶ anac-metar-dlq  (inválidas, com o motivo)          │
                                                                                        │
SERVING                                                                                 │
                                                                                        │
  Cliente ── HTTP POST (voo + clima) ──▶ Cloud Run: anac-api ── /predict ───────────────┘
                                                             └─ /explain ─▶ BigQuery ML
```

- **Batch** organiza 9 anos de voos e clima em camadas Medallion, junta a
  observação METAR mais recente antes de cada partida e treina o modelo.
- **Streaming** recebe cada observação nova, valida contra o contrato de
  features e grava no mesmo dataset do histórico. Mensagens fora do contrato vão
  para um tópico de dead-letter, com o payload original e o motivo.
- **Serving**: a API valida o pedido, consulta o endpoint do Vertex AI e devolve
  a probabilidade. O modelo é registrado direto do BigQuery ML no Vertex, sem
  exportar arquivo.

[`schemas/features.json`](schemas/features.json) é o contrato único de features,
usado pela Gold, pelo `CREATE MODEL`, pela API e pelo Dataflow: 10 variáveis do
voo e 9 de clima.

### Particionamento

| Tabela | Partição | Cluster | Por quê |
| --- | --- | --- | --- |
| Bronze (VRA, METAR) | data de ingestão (pasta no GCS) | — | cada lote é reprocessável isoladamente |
| Silver e Gold de voos | dia do voo | companhia, aeroporto de origem | consultas e corte de treino filtram por período |
| Silver de METAR | dia da observação | aeroporto | o cruzamento com voos busca um aeroporto numa janela de horas |
| `tb_anac_stream_metar` | dia do evento | aeroporto | o monitoramento lê só o dia corrente |

## Estrutura do repositório

```text
api/                  # API FastAPI + Dockerfile + cloudbuild.yaml (Cloud Run)
streaming/
  producer/           # gerador de eventos METAR -> Pub/Sub
  dataflow/           # pipeline Apache Beam: Pub/Sub -> validacao -> BigQuery + dead-letter
schemas/features.json # contrato de features (fonte unica)
sql/
  setup/ bronze/ silver/ gold/ ml/ streaming/   # uma pasta por camada
scripts/              # ingestao batch: download, validacao de contagem, upload ao GCS
  t2/                 # liga/desliga dos recursos do T2 e comandos da demo
notebooks/            # criacao da Bronze e da Silver de voos (T1)
terraform/            # Pub/Sub, Artifact Registry, buckets
docs/                 # PRD, enunciados, guia de operacao, apresentacoes
```

## Como executar

Pré-requisitos: `gcloud` autenticado (`gcloud auth login --update-adc`),
[`uv`](https://docs.astral.sh/uv/) e `terraform` ≥ 1.9. Copie `.env.example` para
`.env` e preencha `PROJECT_ID`.

### Pipeline batch

```bash
uv run python scripts/baixar_dados.py               # CSVs mensais do VRA
uv run python scripts/ingest_bronze_vra_to_gcs.py   # upload com validacao de contagem
uv run python scripts/baixar_metar.py               # historico METAR da IEM
uv run python scripts/ingest_bronze_metar_to_gcs.py
```

Depois, os SQL na ordem das camadas: `sql/setup` → `sql/bronze` → `sql/silver` →
`sql/gold` → `sql/ml`. O SQL novo usa `${PROJECT_ID}`, substituído com
`envsubst`.

### Infraestrutura, streaming e API

```bash
cd terraform && terraform init -backend-config="bucket=<PROJECT_ID>-anac-tfstate" && terraform apply && cd ..
./scripts/t2/metar_table.sh            # tabela de destino do streaming
./scripts/t2/vertex_register.sh        # registra o modelo no Vertex Model Registry

./scripts/t2/vertex_deploy.sh          # implanta o modelo no endpoint (cobrado por hora)
./scripts/t2/api_deploy.sh             # build da imagem e deploy no Cloud Run
./scripts/t2/dataflow_start_metar.sh   # liga o pipeline de streaming (cobrado por hora)
./scripts/t2/simulate_metar.sh         # gerador: publica observacoes no Pub/Sub
```

Desligar ao terminar: `dataflow_drain_metar.sh` e `vertex_undeploy.sh`. Guia
completo, com custos e roteiro da demo: [`docs/t2-operacao.md`](docs/t2-operacao.md).

### Testes

```bash
(cd api && uv run --group dev pytest -q)
(cd streaming/dataflow && uv run --no-project --with-requirements requirements.txt --with pytest python -m pytest -q tests)
(cd streaming/producer && uv run --no-project --with "apache-beam[gcp]==2.77.0" --with-requirements requirements.txt --with pytest python -m pytest -q tests)
```

## Chamar a API

A API no Cloud Run é **privada**: não aceita chamada anônima e responde 403 sem
token. O motivo é custo e segurança: o repositório é público e o endpoint do
Vertex AI é cobrado por uso. Quem tem acesso ao projeto chama com o token de
identidade do `gcloud`:

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
     -H "Content-Type: application/json" \
     -d '{"sg_empresa_icao":"GLO","sg_icao_origem":"SBGO","sg_icao_destino":"SBGR",
          "cd_tipo_linha":"N","sg_equipamento_icao":"B738","dia_semana":"2","mes":"12",
          "nr_assentos_ofertados":186,"hora_partida_prevista":13,"duracao_prevista_min":75,
          "clima_temperatura_c":25.0,"clima_umidade_relativa_pct":73.8,
          "clima_velocidade_vento_kmh":18.5,"clima_rajada_vento_kmh":40.7,
          "clima_visibilidade_m":9994.0,"clima_pressao_hpa":1015.9,
          "clima_cobertura_nuvens":"FEW","clima_altura_nuvens_m":762.0,
          "clima_fenomenos":"-TSRA"}' \
     https://anac-api-67210160247.us-central1.run.app/predict
```

Resposta: `{"prob_atraso": 0.61, "modelo": "vertex:...", "latencia_ms": ..., ...}`.
A documentação interativa, com exemplos prontos, fica em `/docs`. Rotas:
`GET /health`, `POST /predict` e `POST /explain` (peso de cada variável na
previsão).

## Os dados

| | Voos (VRA/ANAC) | Meteorologia (METAR) |
| --- | --- | --- |
| Fonte | CSVs mensais em `siros.anac.gov.br` | Iowa Environmental Mesonet, rede `BR__ASOS` |
| Frequência | um arquivo por mês | uma observação por hora por aeroporto |
| Recorte | 2016–2024: 6,19 milhões de voos na Gold | 2016–2024: 6,47 milhões de observações, 127 estações |
| Autenticação | nenhuma | nenhuma |

Ressalvas que moldaram o projeto:

- **O schema do CSV do VRA não é fixo**: 20 ou 21 colunas conforme o mês e
  `dt_referencia` em dois formatos. Tratado na Bronze e na Silver
  ([`docs/bronze_silver.md`](docs/bronze_silver.md)).
- **HTTP 200 não prova dado completo.** Toda ingestão valida contagem e tamanho
  antes de persistir.
- **O VRA está em horário de Brasília** para todos os aeroportos; a conversão
  para UTC, necessária para cruzar com o METAR, é um deslocamento fixo de 3 h.
- **Sem vazamento de alvo.** Só entram no modelo atributos conhecidos antes da
  decolagem; horário real e situação do voo são proibidos como entrada.

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [`docs/t2-operacao.md`](docs/t2-operacao.md) | Como ligar, desligar e demonstrar o T2 |
| [`docs/PRD.md`](docs/PRD.md) | Requisitos, métricas, modelo de dados e decisões |
| [`docs/bronze_silver.md`](docs/bronze_silver.md) | Tratamento do schema instável do VRA |
| [`docs/enunciados/`](docs/enunciados/) | Transcrição dos três enunciados |

## Equipe

- Igor Reis Braziel
- João Henrique F. Simielli
- Bruno Moreira Lavalli Calura
- João Pedro de Castro Gomes Fernandes

## Segurança

Nenhuma credencial, chave de serviço ou token é versionado; a configuração local
fica em `.env` e `terraform/terraform.tfvars`, fora do Git. O id do projeto GCP
aparece no código e na documentação, o que não dá acesso a nada sem credencial.
