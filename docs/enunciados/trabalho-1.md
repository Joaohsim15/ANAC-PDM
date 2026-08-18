# Trabalho 1 — Arquitetura Medallion e BigQuery ML

> Transcrição do enunciado publicado na Plataforma Turing (INF/UFG), disciplina
> **PDM_BIA**. O texto foi preservado na íntegra; apenas os elementos de
> navegação da plataforma foram removidos.

| Item | Valor |
| --- | --- |
| Disciplina | PDM_BIA — Processamento de Dados Massivos (INF/UFG, Graduação, Inteligência Artificial) |
| Abertura | quinta-feira, 13 ago. 2026, 00:00 |
| Vencimento | sexta-feira, 11 set. 2026, 00:00 |
| Data de apresentação | 11/09/2026 |
| Tempo de apresentação | 5 minutos (estourar zera o quesito) |
| Tamanho do grupo | até 4 alunos |
| Peso | Apresentação 20% · Aplicação prática 60% · Código 20% |

---

## 1 — Introdução

O Trabalho 1 visa avaliar a capacidade de criação de uma arquitetura de dados
moderna na nuvem (GCP) com processamento ETL/ELT utilizando a Arquitetura
Medallion e a criação de modelos de Machine Learning utilizando puramente SQL no
BigQuery ML.

## 2 — Dados gerais

- **Data de apresentação:** 11/09/2026
- **Tamanho dos grupos:** o trabalho deverá ser realizado em grupos de até 4
  alunos. Apenas um aluno do grupo precisa apresentar.
- **Tempo de apresentação:** cada grupo terá no máximo 5 minutos para apresentar
  a arquitetura e os resultados.
  > **Atenção:** se o grupo ultrapassar o tempo limite de 5 minutos, receberá
  > nota zero no quesito de tempo/apresentação.
- **Tema e dados:** tema e os dados são de livre escolha do grupo.
- **Ambiente de execução:** o trabalho deve estar rodando em produção na nuvem no
  dia da apresentação para que o grupo possa obter a nota prática. O pipeline e a
  consulta ao modelo de ML deverão ser demonstrados ao vivo.

## 3 — Descrição do trabalho

**Objetivo:** desenvolver uma solução de processamento de dados massivos em lote
(batch) utilizando a Arquitetura Medallion no BigQuery e treinar um modelo
preditivo com BigQuery ML.

**Escopo:**

1. **Escolha do domínio de negócio:** o grupo pode escolher o tema que quiser
   (ex.: varejo, saúde, finanças, entretenimento, etc.).
2. **Coleta e ingestão de dados:** ingestão de um dataset real no Google Cloud
   Storage (GCS) em seu formato bruto.
3. **Processamento ELT e Arquitetura Medallion:** utilizar o poder computacional
   do BigQuery para processar e estruturar as camadas de dados:
   - **Bronze:** dados brutos / ingestão inicial.
   - **Silver:** dados limpos, filtrados e enriquecidos.
   - **Gold:** dados agregados e prontos para modelagem e inteligência de
     negócios.
4. **Modelagem e ML com BigQuery ML:** a partir da camada Gold, criar, treinar e
   avaliar um modelo inicial de mineração de dados (classificação, regressão ou
   clusterização) usando puramente BigQuery ML (SQL).

## 4 — Entregáveis

Arquivo compactado (`.zip`) contendo:

- **Código-fonte / scripts:** scripts SQL e código de ingestão/automação
  hospedados em repositório no GitHub.
- **Apresentação (PDF):** slides da apresentação.

## 5 — Critérios de avaliação

### Apresentação (20% da nota)

- Foco na execução do pipeline da arquitetura Medallion.
- Apenas um integrante do grupo precisa apresentar.

> **Observação:** se o grupo ultrapassar o tempo limite de 5 minutos, receberá
> nota zero neste quesito.

### Aplicação prática (60% da nota)

- A solução deve estar rodando na nuvem no dia da apresentação.
- Demonstração da execução das consultas das camadas Medallion no BigQuery e
  predição utilizando o BigQuery ML.

### Código (20% da nota)

- Organização do projeto, estrutura dos arquivos `.sql` e qualidade da
  arquitetura do pipeline.
