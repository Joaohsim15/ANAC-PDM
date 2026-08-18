# ANAC-PDM — Predição de Atraso de Voos

Plataforma de dados e MLOps na Google Cloud que prediz, **antes da decolagem**, a
probabilidade de um voo comercial brasileiro partir com mais de 15 minutos de
atraso. Construída sobre a **API oficial do VRA (Voo Regular Ativo)** da ANAC.

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

```
API VRA/ANAC ─▶ GCS (raw) ──▶ Bronze ──▶ Silver ──┬──▶ Gold agg_*  ──▶ Looker Studio
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
| Fonte | API REST oficial do VRA (`sas.anac.gov.br/sas/vra_api`) — JSON, sem autenticação |
| Armazenamento bruto | Google Cloud Storage |
| Data warehouse | BigQuery (Medallion: Bronze / Silver / Gold) |
| Machine learning | BigQuery ML → Vertex AI Model Registry + Endpoint |
| Serviço de predição | FastAPI no Cloud Run |
| Streaming | Pub/Sub + Dataflow (Apache Beam) |
| Orquestração | n8n no Cloud Run, com estado em Cloud SQL Postgres |
| BI | Looker Studio |

## Os dados

Verificado em 18/08/2026 contra 81.119 registros reais de junho/2026.

| | |
| --- | --- |
| Acesso | `GET https://sas.anac.gov.br/sas/vra_api/vra?dt_referencia1=…&dt_referencia2=…` |
| Autenticação | Nenhuma |
| Campos | 20, todos como string — a tipagem é trabalho da Silver |
| Volume | ≈ 2.300–2.900 voos/dia · ≈ 81 mil/mês · ≈ 63 MB/mês |
| Defasagem | ≈ 7 semanas entre o voo e a publicação |
| Taxa de atraso > 15 min | 18,7% |

Duas ressalvas que moldaram o projeto:

- **Os CSVs do portal `gov.br` não são baixáveis por script.** O portal está atrás
  de um WAF que devolve um desafio JavaScript no lugar do arquivo. A API do
  SAS/ANAC não tem essa barreira — e ainda traz 20 campos contra 11 do CSV.
- **A API trunca respostas sem sinalizar erro.** A mesma chamada devolveu 841 e
  depois 2.768 registros, ambas com HTTP 200. A ingestão valida a contagem de cada
  lote antes de persistir; tratar HTTP 200 como sucesso levaria a treinar o modelo
  sobre um mês incompleto, sem sintoma visível.

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [`docs/PRD.md`](docs/PRD.md) | Documento de requisitos: escopo, requisitos funcionais e não funcionais, métricas-alvo, modelo de dados, glossário, riscos, cronograma e critérios de aceite |
| [`docs/enunciados/`](docs/enunciados/) | Transcrição fiel dos três enunciados da disciplina |

## Estrutura planejada do repositório

```
terraform/                  # infraestrutura declarada, mínima
ingestion/                  # batch: consome a API do VRA, valida, grava no GCS
streaming/
  producer/                 # simulador de eventos → Pub/Sub
  dataflow/                 # pipeline Beam
sql/
  00_setup/  10_bronze/  20_silver/  30_gold/  40_ml/
api/                        # FastAPI + Dockerfile (Cloud Run)
orchestration/              # workflows n8n
schemas/features.json       # contrato de features
docs/
```

O prefixo numérico nas pastas de SQL indica a ordem de execução.

> **Estado atual:** apenas a documentação existe. As pastas de código serão
> criadas conforme o cronograma do PRD.

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
