# Trabalho 2 — Ingestão em Tempo Real e Deploy de Modelo

> Transcrição do enunciado publicado na Plataforma Turing (INF/UFG), disciplina
> **PDM_BIA**. O texto foi preservado na íntegra; apenas os elementos de
> navegação da plataforma foram removidos.

| Item | Valor |
| --- | --- |
| Disciplina | PDM_BIA — Processamento de Dados Massivos (INF/UFG, Graduação, Inteligência Artificial) |
| Abertura | quinta-feira, 13 ago. 2026, 00:00 |
| Vencimento | sexta-feira, 23 out. 2026, 00:00 |
| Data de apresentação | 23/10/2026 |
| Tempo de apresentação | 5 minutos (estourar zera o quesito) |
| Tamanho do grupo | até 4 alunos |
| Peso | Apresentação 20% · Aplicação prática 60% · Código 20% |

---

## 1 — Introdução

O Trabalho 2 visa evoluir a arquitetura do projeto incorporando o processamento
de dados em tempo real (streaming) e o deploy de modelos de Machine Learning no
Vertex AI servidos via API REST no Cloud Run.

## 2 — Dados gerais

- **Data de apresentação:** 23/10/2026
- **Tamanho dos grupos:** o trabalho deverá ser realizado em grupos de até 4
  alunos. Apenas um aluno do grupo precisa apresentar.
- **Tempo de apresentação:** cada grupo terá no máximo 5 minutos para apresentar
  a arquitetura e os resultados.
  > **Atenção:** se o grupo ultrapassar o tempo limite de 5 minutos, receberá
  > nota zero no quesito de tempo/apresentação.
- **Tema e dados:** tema e os dados são de livre escolha do grupo (pode
  **continuar o projeto do Trabalho 1** ou criar um novo).
- **Ambiente de execução:** o trabalho deve estar rodando em produção na nuvem no
  dia da apresentação para que o grupo possa obter a nota prática. A ingestão em
  streaming e a API REST deverão ser demonstradas ao vivo.

## 3 — Descrição do trabalho

**Objetivo:** desenvolver uma evolução incremental da arquitetura integrando um
pipeline de streaming em tempo real (Pub/Sub + Dataflow) e implantando o modelo
de IA no Vertex AI com serviço de predição via API REST no Cloud Run.

**Escopo:**

1. **Escolha do domínio de negócio:** o grupo pode escolher o tema que quiser
   (ex.: varejo, saúde, finanças, entretenimento, etc.).
2. **Pipeline de tempo real (streaming):** construir um pipeline de streaming
   utilizando Pub/Sub + Dataflow para capturar novos eventos e salvar os dados no
   BigQuery.
3. **Deploy no Vertex AI:** implantar o modelo de Machine Learning treinado no
   ambiente do Vertex AI.
4. **Serviço de predição (API REST):** criar uma API REST hospedada no Cloud Run
   integrada ao Vertex AI para receber requisições e servir predições em tempo
   real.

## 4 — Entregáveis

Arquivo compactado (`.zip`) contendo:

- **Código-fonte / scripts:** código do pipeline Dataflow, códigos da API REST e
  configurações do Pub/Sub / Vertex AI hospedados em repositório no GitHub.
- **Apresentação (PDF):** slides da apresentação.

## 5 — Critérios de avaliação

### Apresentação (20% da nota)

- Foco na ingestão em tempo real e na arquitetura de deploy da API do modelo.
- Apenas um integrante do grupo precisa apresentar.

> **Observação:** se o grupo ultrapassar o tempo limite de 5 minutos, receberá
> nota zero neste quesito.

### Aplicação prática (60% da nota)

- A solução deve estar rodando na nuvem no dia da apresentação.
- Demonstração do envio de eventos via Pub/Sub / Dataflow salvando no BigQuery e
  chamada HTTP para a API no Cloud Run obtendo a predição.

### Código (20% da nota)

- Organização do repositório, qualidade do código da API no Cloud Run e scripts
  do pipeline de streaming.
