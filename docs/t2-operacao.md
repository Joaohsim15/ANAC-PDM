# Trabalho 2 — como rodar, ligar e desligar

Guia operacional do streaming e da API de predição. Os comandos rodam a partir
da raiz do repositório e leem as variáveis de `.env`. Copie `.env.example`, que
não leva valores reais.

```bash
cp .env.example .env   # preencha PROJECT_ID; o resto tem padrão
```

Pré-requisitos: `gcloud` autenticado (`gcloud auth login --update-adc`), `uv`,
`terraform` ≥ 1.9 e `docker` (opcional, para testar a imagem localmente).

---

## 1. O que existe e onde

```mermaid
flowchart LR
    subgraph stream["Streaming de METAR"]
        SIM["Simulador<br/>streaming/producer/simulator_metar.py"] --> TOP[("Pub/Sub<br/>anac-metar")]
        TOP --> SUB["assinatura<br/>anac-metar-dataflow"]
        SUB --> DF["Dataflow --domain metar<br/>streaming/dataflow"]
        DF --> BQ[("BigQuery<br/>tf_anac.tb_anac_stream_metar")]
        DF -->|fora do contrato| DLQ[("Pub/Sub<br/>anac-metar-dlq")]
    end
    subgraph serving["Predição"]
        CLI["curl"] --> API["Cloud Run<br/>anac-api"]
        API -->|/predict| EP["Vertex AI Endpoint<br/>anac-atraso-endpoint"]
        API -->|/explain| BQML
        API -.->|log em segundo plano| LOG[("BigQuery<br/>tb_anac_predicoes_log")]
        BQML["BigQuery ML<br/>mdl_anac_m1_boosted_tree"] -->|registro direto| REG["Model Registry<br/>anac_m1_boosted_tree"]
        REG --> EP
    end
```

| Peça | Código | Criada por |
| --- | --- | --- |
| Contrato de features | `schemas/features.json` | — |
| Tópicos, assinaturas, repositório de imagens, bucket do Dataflow | `terraform/` | `terraform apply` (uma vez) |
| Tabela de observações de METAR | `sql/streaming/create_table_stream_metar.sql` | `scripts/t2/metar_table.sh` (uma vez) |
| Tabela do log de predições | `sql/ml/create_table_predicoes_log.sql` | `bq query` (uma vez) |
| Simulador de METAR | `streaming/producer/simulator_metar.py` | — |
| Pipeline Beam | `streaming/dataflow/pipeline/` (`--domain metar`) | `scripts/t2/dataflow_start_metar.sh` |
| Modelo no Vertex | `ALTER MODEL ... vertex_ai_model_id` | `scripts/t2/vertex_register.sh` (uma vez) |
| Endpoint com o modelo implantado | — | `scripts/t2/vertex_deploy.sh` |
| API | `api/` | `scripts/t2/api_deploy.sh` |

O streaming e a API são **independentes** nesta entrega: o Dataflow não chama a
API. Se um dos dois falhar na apresentação, o outro continua de pé.

Os voos seguem em batch (Medallion do T1). A ingestão em streaming é a de
observações meteorológicas (METAR). O streaming de voos foi removido do
código; os tópicos `anac-voos*` ainda existem no Terraform, ociosos e sem custo,
até um `apply` planejado depois da apresentação.

---

## 2. Infraestrutura base (uma vez)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars          # preencha project_id
terraform init -backend-config="bucket=<PROJECT_ID>-anac-tfstate"
terraform plan -out t2.tfplan && terraform apply t2.tfplan
cd ..
./scripts/t2/metar_table.sh
PROJECT_ID=<PROJECT_ID> envsubst '${PROJECT_ID}' < sql/ml/create_table_predicoes_log.sql \
  | bq query --nouse_legacy_sql
./scripts/t2/vertex_register.sh
```

O Terraform só cria recursos com prefixo `anac-` e nunca importa nem altera os
exercícios de aula que existem no mesmo projeto. O bucket do state é criado à
mão, uma única vez: o Terraform não pode guardar o state no próprio recurso que
ele cria.

`manage_iam = true` cria service accounts dedicadas (`anac-api`,
`anac-dataflow`) com papéis mínimos. Exige quem administre IAM no projeto
(Owner). Com `false`, que é o padrão, Cloud Run e Dataflow usam a conta padrão
do Compute Engine. Depois de aplicar com `true`, preencha `API_SERVICE_ACCOUNT`
e `DATAFLOW_SERVICE_ACCOUNT` no `.env`.

---

## 3. Liga e desliga — controle de custo

| Recurso | Cobrança | Liga | Desliga |
| --- | --- | --- | --- |
| Modelo no endpoint do Vertex | **por hora implantado** (≈ US$ 0,10/h em `n1-standard-2`) | `vertex_deploy.sh` (15 a 35 min; 33 min em 09/10) | `vertex_undeploy.sh` |
| Job Dataflow | **por hora ligado** | `dataflow_start_metar.sh` (~4 min) | `dataflow_drain_metar.sh` |
| Cloud Run | por uso; escala a zero | `api_deploy.sh --demo` (1 instância quente) | `api_deploy.sh` (volta a zero) |
| Pub/Sub, BigQuery, Artifact Registry | desprezível no volume da demo | — | — |

Regras:

- O endpoint fica ligado **só na véspera da apresentação (22/10, à noite) até o
  fim dela em 23/10**.
- Desimplantar não apaga o endpoint: o id continua o mesmo, e a API já
  publicada volta a responder assim que o modelo é reimplantado, sem novo deploy.
- `dataflow_start_metar.sh` devolve o terminal assim que o job é submetido. O
  job ainda leva uns 4 min até o worker processar eventos: espere antes de
  rodar o simulador.
- Todo teste com Dataflow termina com `dataflow_drain_metar.sh`. O drain processa o
  que já chegou antes de encerrar, então nenhum evento se perde.
- Ao fim de cada sessão de trabalho, confira o console: Vertex AI → Endpoints
  (nenhum modelo implantado) e Dataflow → Jobs (nenhum `Running`).

---

## 4. Roteiro da demo (5 min)

A demonstração é feita pelo console do GCP. Duas peças não sobem pelo console e
ficam ligadas antes, por terminal: o job do Dataflow (o pipeline é Python) e o
modelo no endpoint do Vertex.

Na véspera (22/10, à noite):

```bash
./scripts/t2/vertex_deploy.sh        # leva de 15 a 35 min
./scripts/t2/predict.sh              # confere a paridade: 0,613587
```

No dia (até 30 min antes):

```bash
./scripts/t2/api_deploy.sh --demo    # min-instances=1: sem cold start
./scripts/t2/dataflow_start_metar.sh # volta em ~16 s; o worker leva ~4 min
./scripts/t2/simulate_metar.sh --limite 100 --por-segundo 5   # carga inicial
```

Para abrir a API privada no navegador, no Cloud Shell:

```bash
gcloud run services proxy anac-api --project <PROJECT_ID> --region us-central1 --port 8080
```

Depois, *Visualização na Web → porta 8080* e `/docs` no fim do endereço. As
rotas `/predict` e `/explain` trazem exemplos prontos (`com_trovoada`,
`sem_estacao`, `invalido`).

Ao vivo, pelo console:

| Onde | Ação | O que mostrar |
| --- | --- | --- |
| Dataflow → `anac-stream-metar` | abrir o job | pipeline em execução |
| Pub/Sub → `anac-metar` → Mensagens | publicar a mensagem válida abaixo | observação entrando no tópico |
| BigQuery | rodar `sql/streaming/monitor_stream_metar.sql` | contagem e lag em segundos |
| Pub/Sub → `anac-metar` → Mensagens | publicar a mensagem inválida abaixo | valor fora do contrato |
| Pub/Sub → `anac-metar-dlq-inspecao` → Mensagens | Pull | a mensagem recusada, com o motivo |
| Vertex AI → Endpoints | abrir `anac-atraso-endpoint` | modelo versão 2 implantado |
| `/docs` da API | `/predict` com `com_trovoada` e `sem_estacao` | 0,6136 e 0,6026 |
| `/docs` da API | `/explain` com `com_trovoada` | peso de cada variável |
| `/docs` da API | `/predict` com `invalido` | HTTP 422 |

Mensagem válida:

```json
{"event_id":"demo-ui-1","event_ts":"2026-10-23T14:00:00Z","sg_icao":"SBGO","dt_observacao_utc":"2026-10-23T13:00:00","clima_temperatura_c":27.0,"clima_umidade_relativa_pct":74.0,"clima_velocidade_vento_kmh":14.8,"clima_visibilidade_m":9999.0,"clima_pressao_hpa":1012.0,"clima_cobertura_nuvens":"SCT","clima_altura_nuvens_m":900.0,"clima_fenomenos":"TS"}
```

Mensagem inválida (vai para o dead-letter):

```json
{"event_id":"demo-ui-2","event_ts":"2026-10-23T14:00:00Z","sg_icao":"SBGO","clima_cobertura_nuvens":"XXX"}
```

O Pull da assinatura de dead-letter consome a mensagem: ela aparece uma vez só.

Depois da apresentação, no mesmo dia:

```bash
./scripts/t2/dataflow_drain_metar.sh
./scripts/t2/vertex_undeploy.sh
./scripts/t2/api_deploy.sh           # volta a escalar a zero
```

---

## 5. Decisões de implementação

**Registro direto do BigQuery ML no Vertex.** O `ALTER MODEL ... SET OPTIONS
(vertex_ai_model_id = ...)` publica no Model Registry o modelo **vigente** no
BigQuery, e o container do Vertex faz o pré-processamento das categorias. O
artefato exportado no GCS (`gs://dados-anac-vra/models/m1_boosted_tree/`) é de
um treino anterior: foi exportado em 10/09 às 14:43 UTC, antes do treino final
de 11/09. Por isso ele dá 0,634 para o voo de exemplo, enquanto o `ML.PREDICT`
dá 0,608. Servir pelo registro direto elimina essa divergência.

**Contrato tolerante ao dado real.** `schemas/features.json` aceita 99,97% da
Gold (6.185.567 de 6.187.534 linhas). As 1.967 recusadas são sujeira do
histórico: assentos negativos, equipamento nulo, tipo de linha vazio.
`cd_tipo_linha` aceita qualquer letra. O modelo só aprendeu C, G, I, N e X, mas
R, E, L e H aparecem em 2,4% dos voos, e o modelo os trata como valor ausente
sem quebrar. Recusá-los mandaria voos reais para o dead-letter durante a demo.

**O simulador não publica o que o contrato recusa.** A consulta do simulador
deriva os filtros do próprio contrato. A demonstração do dead-letter é um passo
explícito (`--invalido`), em vez de depender de uma linha suja aparecer por
acaso.

**Dead-letter dentro do pipeline.** O pipeline publica em `anac-metar-dlq`
toda mensagem que viola o contrato, com o motivo e o payload original. A
política de dead-letter nativa do Pub/Sub não é usada, porque exige conceder
papéis à conta de serviço do Pub/Sub.

**Escrita no BigQuery por streaming inserts.** A Storage Write API do Beam não
converte colunas `DATETIME` em schema explícito. Os streaming inserts aceitam
`DATETIME` e `TIMESTAMP` como texto ISO e gravam em segundos (lag medido de 3 s
em média).

**`/explain` fora do caminho crítico.** O `/predict` chama o Vertex. O
`/explain` roda `ML.EXPLAIN_PREDICT` no BigQuery, leva de 1 a 3 s e fica num
endpoint separado, para não pesar na latência medida. O log de cada predição em
`tb_anac_predicoes_log` é gravado depois da resposta e não a atrasa.

**API privada.** O Cloud Run não aceita chamadas anônimas; a demo usa o token
de identidade do `gcloud` (`predict.sh`). O repositório é público e o endpoint
do Vertex é cobrado. Uma URL aberta seria abuso esperando para acontecer.

**Cota das bibliotecas Python.** Os scripts fixam `GOOGLE_CLOUD_QUOTA_PROJECT`
no projeto do trabalho. As credenciais ADC de quem roda podem apontar a cota
para outro projeto pessoal, e então o Dataflow recusa o job com
`SERVICE_DISABLED` em um projeto que não é o nosso.

---

## 6. Testes

```bash
(cd api && uv run --group dev pytest -q)
(cd streaming/dataflow && uv run --no-project --with-requirements requirements.txt --with pytest python -m pytest -q tests)
(cd streaming/producer && uv run --no-project --with "apache-beam[gcp]==2.77.0" --with pytest python -m pytest -q tests)
```

Os testes do pipeline rodam o `DoFn` no DirectRunner, sem Pub/Sub nem BigQuery.
O teste do simulador confere que todo evento que ele publica passa na validação
do pipeline: os dois compartilham o contrato.
