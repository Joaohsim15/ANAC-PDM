# Trabalho 2 — Ingestão em Tempo Real e Deploy de Modelo

> Transcrição do enunciado publicado na Plataforma Turing (INF/UFG), disciplina
> **PDM_BIA**. O texto foi preservado na íntegra; apenas os elementos de
> navegação da plataforma foram removidos. Atualizada em 21/10/2026: a versão
> anterior desta transcrição tinha limite de 5 minutos e critérios mais curtos.

| Item | Valor |
| --- | --- |
| Disciplina | PDM_BIA — Processamento de Dados Massivos (INF/UFG, Graduação, Inteligência Artificial) |
| Abertura | quinta-feira, 13 ago. 2026, 00:00 |
| Vencimento | quinta-feira, 22 out. 2026, 23:59 |
| Data de apresentação | 23/10/2026 |
| Tempo de apresentação | 10 minutos (estourar zera o quesito) |
| Tamanho do grupo | até 4 alunos; apenas um precisa apresentar |
| Peso | Apresentação 20% · Aplicação prática 60% · Código 20% |

---

## 1 — Introdução

O Trabalho 2 é uma evolução incremental do Trabalho 1. O objetivo principal é
transformar a solução batch em uma arquitetura híbrida de dados (Batch +
Streaming), garantindo a disponibilidade contínua de dados por meio de um
pipeline de processamento em tempo real, além de avançar na esteira de MLOps
com o deploy e disponibilização do modelo preditivo via API REST em nuvem.

## 2 — Dados gerais

- **Data de apresentação:** 23/10/2026
- **Data de entrega:** 22/10/2026 (até 23:59)
- **Tamanho dos grupos:** grupos de até 4 alunos. Apenas um integrante precisa
  apresentar.
- **Tempo de apresentação:** cada grupo terá no máximo 10 minutos para
  apresentar a arquitetura e os resultados práticos.
  > **Atenção:** se o grupo ultrapassar o tempo limite de 10 minutos, receberá
  > nota zero no quesito de apresentação.
- **Temas:** o grupo deve continuar com o domínio de negócio e dataset do
  Trabalho 1, expandindo-o para contemplar eventos em tempo real. Caso haja
  justificativa técnica para troca de domínio, esta deverá ser previamente
  alinhada com o professor.
- **Ambiente de execução:** toda a solução deve estar rodando em produção na
  nuvem (Google Cloud Platform) no dia da apresentação. A ingestão contínua em
  streaming e a API REST deverão ser demonstradas ao vivo.

## 3 — Descrição do trabalho

**Objetivo:** evoluir a arquitetura do Trabalho 1 integrando um pipeline de
streaming em tempo real para processar dados contínuos lado a lado com a base
histórica em lote (BigQuery), além de registrar o modelo preditivo no Vertex AI
e disponibilizar um serviço de inferência em tempo real via API REST no Cloud
Run.

**Escopo do projeto:**

1. **Streaming:** os dados devem estar disponíveis e fluindo continuamente. O
   grupo pode disponibilizar um produtor/gerador de eventos (ex.: script Python
   simulando dispositivos IoT, transações de clientes ou registros em tempo
   real) que envie mensagens em formato JSON para um tópico do Google Cloud
   Pub/Sub.
2. **Pipeline de processamento em tempo real:**
   - Construção de um pipeline de processamento de dados em streaming.
   - O pipeline deve consumir as mensagens do Pub/Sub, aplicar
     transformações/limpezas em tempo real e salvar os dados processados em
     tabelas específicas no BigQuery.
   - **Batch + Streaming:** no BigQuery, deve ficar evidente a relação entre os
     dados históricos processados em lote e as novas tabelas/partições
     alimentadas continuamente pelo streaming.
3. **Deploy de modelo no Vertex AI:** o modelo de Machine Learning deve ser
   registrado no Vertex AI Model Registry ou disponibilizado como um artefato
   pronto para produção.
4. **Serviço de predição em produção (API REST no Cloud Run):**
   - Criação de uma API REST.
   - A API deve estar conteinerizada (Docker) e hospedada como serviço
     serverless no Google Cloud Run.
   - A API deve receber requisições HTTP (POST) com dados de entrada, carregar o
     modelo (ou consultar o endpoint do Vertex AI) e retornar a
     inferência/predição em formato JSON em tempo real.

## 4 — Entregáveis

Apresentação no formato PDF, onde se pode adicionar o link do GitHub na
apresentação para avaliação do código.

- **Apresentação (PDF):** slides sintetizando a evolução da arquitetura do
  Trabalho 1 para o Trabalho 2, o diagrama da arquitetura híbrida e evidências
  dos testes.
- **Link do código no GitHub** contendo:
  - Código do produtor/simulador de eventos Pub/Sub.
  - Código do pipeline de streaming.
  - Código da API REST (incluindo Dockerfile, requirements.txt e scripts de
    deploy no Cloud Run).
  - Scripts SQL das tabelas de streaming e integração no BigQuery.
  - Documentação clara no README.md explicando a arquitetura e como executar os
    componentes.
- **Link do modelo rodando no Cloud Run.**

## 5 — Critérios de avaliação

### Apresentação (20% da nota)

- Clareza na explicação da arquitetura integrada de ponta a ponta (Batch +
  Streaming).
- Justificativa das escolhas técnicas de particionamento e processamento.
- Cumprimento do tempo de apresentação (máximo de 10 minutos).

### Aplicação prática ao vivo (60% da nota)

- **Pipeline de dados e disponibilidade (30%):** demonstração ao vivo do
  gerador enviando dados para o Pub/Sub, o processador de eventos consumindo e
  processando em streaming, e a persistência em tempo real. Demonstrar os
  pipelines batch e streaming e demonstrar o papel de cada pipeline.
- **Serviço de inferência Cloud Run (30%):** teste de requisição HTTP em tempo
  real (via Postman, cURL ou script) chamando a API no Cloud Run e obtendo a
  predição do modelo com baixa latência.

### Código e organização (20% da nota)

- Boas práticas de desenvolvimento, legibilidade do pipeline, estrutura do
  Dockerfile e organização modular do repositório no GitHub.
