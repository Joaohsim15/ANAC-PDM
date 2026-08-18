# Trabalho Final — Pipeline Completo Integrado e Orquestrado

> Transcrição do enunciado publicado na Plataforma Turing (INF/UFG), disciplina
> **PDM_BIA**. O texto foi preservado na íntegra; apenas os elementos de
> navegação da plataforma foram removidos.

| Item | Valor |
| --- | --- |
| Disciplina | PDM_BIA — Processamento de Dados Massivos (INF/UFG, Graduação, Inteligência Artificial) |
| Abertura | quinta-feira, 21 ago. 2025, 00:00 ¹ |
| Vencimento | sexta-feira, 4 dez. 2026, 22:00 |
| Data de apresentação | 04/12/2026 |
| Tempo de apresentação | 10 minutos (estourar zera o quesito) |
| Tamanho do grupo | até 4 alunos |
| Peso | Apresentação 20% · Aplicação prática 60% · Código 20% |

> ¹ A data de abertura aparece como **2025** no enunciado original, enquanto todas
> as demais datas da disciplina são de 2026. Transcrito fielmente; provável erro
> de digitação na plataforma. Não afeta o vencimento nem a apresentação.

---

## 1 — Introdução

O Trabalho Final visa integrar e automatizar toda a arquitetura de engenharia de
dados e MLOps em tempo real, realizando o enriquecimento de streaming com
inferência instantânea via API e orquestração de fluxos de dados.

## 2 — Dados gerais

- **Data de apresentação:** 04/12/2026
- **Tamanho dos grupos:** o trabalho deverá ser realizado em grupos de até 4
  alunos.
- **Tempo de apresentação:** cada grupo terá no máximo 10 minutos para apresentar
  a arquitetura e os resultados.
  > **Atenção:** se o grupo ultrapassar o tempo limite de 10 minutos, receberá
  > nota zero no quesito de tempo/apresentação.
- **Tema e dados:** tema e os dados são de livre escolha do grupo.
- **Ambiente de execução:** o trabalho deve estar rodando em produção na nuvem no
  dia da apresentação para que o grupo possa obter a nota prática. O fluxo
  automatizado e orquestrado de ponta a ponta deverá ser demonstrado ao vivo.

## 3 — Descrição do trabalho

**Objetivo:** construir uma solução fim a fim onde o pipeline de streaming
(Dataflow) consulta a API do Cloud Run em tempo real para classificar e
enriquecer o dado instantaneamente antes de salvá-lo no BigQuery, com
automação/orquestração com alguma ferramenta similar ao n8n ou Airflow.

**Escopo:**

1. **Escolha do domínio de negócio:** o grupo pode escolher o tema que quiser
   (ex.: varejo, saúde, finanças, entretenimento, etc.).
2. **Integração streaming + IA:** o pipeline de streaming no Dataflow deve
   realizar requisições HTTP para a API no Cloud Run em tempo real, classificando
   o evento instantaneamente.
3. **Enriquecimento e persistência:** o resultado retornado pelo modelo de IA deve
   enriquecer o evento e ser salvo no BigQuery.
4. **Orquestração e automação:** o pipeline completo deve ser automatizado e
   orquestrado com alguma ferramenta similar ao n8n ou Airflow.

## 4 — Entregáveis

Arquivo compactado (`.zip`) contendo:

- **Código-fonte / scripts:** códigos do Dataflow, API REST, workflows do
  orquestrador (n8n/Airflow) e scripts SQL hospedados em repositório no GitHub.
- **Apresentação (PDF):** slides da apresentação.

## 5 — Critérios de avaliação

### Apresentação (20% da nota)

- Foco na arquitetura integrada de ponta a ponta, orquestração e fluxo de tempo
  real.
- Apenas um integrante do grupo precisa apresentar.

> **Observação:** se o grupo ultrapassar o tempo limite de 10 minutos, receberá
> nota zero neste quesito.

### Aplicação prática (60% da nota)

- A solução deve estar rodando na nuvem no dia da apresentação.
- Demonstração do pipeline executando em tempo real chamando a API no Cloud Run,
  enriquecendo o dado, salvando no BigQuery e o fluxo orquestrado via n8n/Airflow.

### Código (20% da nota)

- Organização do repositório, qualidade da integração entre streaming e API, e
  estruturação das DAGs/workflows do orquestrador.
