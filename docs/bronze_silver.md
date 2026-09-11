# Bronze e Silver do VRA — como foram feitas e por quê

Este documento explica as escolhas por trás de `notebooks/raw_to_bronze_vra.ipynb`
e `notebooks/bronze_to_silver_vra.ipynb`. Não repete o PRD — só explica as decisões de
implementação e o que os dados reais (não o schema documentado) obrigaram a
mudar. Para o dicionário de dados e os requisitos formais, ver
[`docs/PRD.md` §10](PRD.md#10-modelo-de-dados).

## Pipeline e nomes reais

```text
vra/*.csv (local, 36 arquivos, recorte 2022-2024)
  → scripts/ingest_bronze_vra_to_gcs.py
  → gs://dados-anac-vra/bronze/vra/raw/_ingested_at=2026-09-03/_batch_id=vra_2022_2024/*.csv
  → notebooks/raw_to_bronze_vra.ipynb
  → pdm-bia-2026.tf_anac.tb_vra_bronze          (external table)
  → notebooks/bronze_to_silver_vra.ipynb
  → pdm-bia-2026.tf_anac.tb_anac_silver         (tabela nativa)
```

Projeto `pdm-bia-2026`, bucket `dados-anac-vra`, dataset `tf_anac`.

---

## Bronze — `tb_vra_bronze`

### Por que external table, e não uma tabela nativa carregada

O RF-002 do PRD trava isso: "a camada Bronze DEVE ser uma external table
sobre o GCS, com todos os campos tipados como `STRING`, append-only". Existe
um notebook de referência de outro dataset do curso
(`Raw_to_bronze.ipynb`, projeto `sd-savio-2026`) que faz o oposto — lê para
pandas, tipa (`TIMESTAMP`), e grava em tabela nativa. Esse padrão é o que o
*nosso* PRD reserva para a Silver, não para a Bronze. `notebooks/raw_to_bronze_vra.ipynb`
segue o RF-002: nenhuma linha é lida para pandas, a "carga" é só metadado —
BigQuery lê o CSV diretamente do GCS a cada query (*schema-on-read*).

### Por que o layout do GCS tem `_ingested_at=`/`_batch_id=` no caminho

RF-004 exige Bronze particionada por data de ingestão, e RF-003 exige que
cada registro carregue `_ingested_at`, `_source_uri` e `_batch_id`. BigQuery
só sabe particionar uma *external table* por meio do próprio caminho no GCS
(partição Hive) — não existe partição por tempo de ingestão automática para
tabelas externas (isso só existe para tabelas nativas carregadas via `LOAD`).

Por isso o notebook primeiro reorganiza os CSVs (upload original em
`raw/VRA_*.csv`, plano) para `raw/_ingested_at=<data>/_batch_id=<lote>/`, e a
`CREATE EXTERNAL TABLE` declara `hive_partitioning.mode = "AUTO"`. Isso
resolve RF-004 (partição) e duas das três colunas de RF-003 de graça, sem
transformação: `_ingested_at` e `_batch_id` viram colunas reais, inferidas do
caminho.

A terceira, `_source_uri`, não usa uma coluna própria — o notebook usa a
pseudo-coluna nativa `_FILE_NAME`, que o BigQuery já expõe em toda query
sobre uma external table, com a mesma informação (URI completo do arquivo de
origem). Isso é uma pequena divergência de nomenclatura em relação ao texto
literal do PRD, documentada aqui — não decidi sozinho mudar a redação do
PRD, mas o dado que RF-003 pede está disponível.

`_batch_id` também não é regravado por linha: em vez de reingerir tudo a
cada mudança, cada lote (ex.: `vra_2022_2024`) é uma pasta própria — a
Bronze é *append-only* nesse sentido: rodar de novo para um recorte novo cria
outra pasta, nunca sobrescreve a anterior.

### Por que `allow_jagged_rows=True` e uma 21ª coluna (`ds_codeshare`)

O schema de 20 campos do PRD §10.2 foi verificado contra a **API REST**
(jun/2026). Os CSVs que efetivamente usamos vêm de outra fonte
(`siros.anac.gov.br`) e **não têm schema fixo**: inspecionando os 36 arquivos
do recorte, 15 têm 21 colunas (a 21ª é `Codeshare`, sempre no fim da linha) e
21 têm 20. A mudança apareceu de forma esporádica em out/2022 e mai/2023, e
ficou definitiva a partir de dez/2023.

Sem tratar isso, `CREATE EXTERNAL TABLE` com um schema fixo de 20 colunas
falha ao ler qualquer arquivo com 21 (`Too many values in line` — foi
exatamente o erro que apareceu na primeira tentativa de leitura). A correção:

- Schema declarado com **21 colunas**, incluindo `ds_codeshare STRING`.
- `external_config.options.allow_jagged_rows = True`, que permite linhas
  "curtas": nos arquivos de 20 colunas, `ds_codeshare` fica `NULL`; nos de
  21, carrega o valor normalmente. Como a coluna nova é sempre *acrescentada
  no fim* (nunca inserida no meio), o mapeamento posicional das 20 colunas
  originais não é afetado em nenhum dos dois formatos.

Essa é a mesma leva de mudança de formato que afeta `dt_referencia` na Silver
(próxima seção) — os dois problemas têm a mesma causa raiz: a fonte real tem
schema drift que o PRD, ancorado na API, não previa.

### Encoding e delimitador do CSV

`field_delimiter=";"`, `skip_leading_rows=1`, `encoding="ISO-8859-1"`. Os
CSVs não são UTF-8 — testado diretamente nos bytes do arquivo, texto como
"Aérea" só decodifica corretamente como Latin-1/CP1252. `ISO-8859-1` foi
escolhido em vez de CP1252 porque é a opção suportada pelo BigQuery para CSV
e porque mapeia todo byte 0x00–0xFF sem erro (CP1252 tem alguns bytes
indefinidos, ex. `0x8D`, que já causaram `UnicodeDecodeError` ao inspecionar
os arquivos localmente com esse encoding).

### Validação (RF-001c / Regra 6 do CLAUDE.md)

A última célula lê o manifest que `scripts/ingest_bronze_vra_to_gcs.py` já
tinha gravado em `gs://dados-anac-vra/bronze/vra/manifest/` durante o upload
(contagem de linhas por arquivo, medida no CSV local antes de qualquer
transformação) e compara com `COUNT(*)` agrupado por lote na Bronze recém
criada. Lê do GCS, não do disco local, porque o notebook roda no Colab — o
disco local ali não tem a pasta `manifests/` do repositório.

---

## Silver — `tb_anac_silver`

### Por que SQL server-side (`CREATE OR REPLACE TABLE ... AS SELECT`), e não pandas

O notebook de referência (`Bronze_to_silver.ipynb`, mesmo projeto
`sd-savio-2026`) lê a Bronze inteira para um DataFrame, aplica uma função de
extração linha a linha e reenvia com `load_table_from_dataframe`. Isso não
dá para replicar aqui por dois motivos:

1. **RF-006 exige `QUALIFY ROW_NUMBER()` literalmente** — é uma cláusula de
   SQL do BigQuery, sem equivalente direto em pandas (`drop_duplicates` não
   satisfaz o requisito como está escrito).
2. **Escala**: o recorte de 3 anos do VRA é da ordem de milhões de linhas,
   bem maior que o dataset de anúncios do notebook de referência. Trazer tudo
   para um DataFrame local antes de regravar seria lento e desnecessário
   quando o próprio BigQuery pode fazer a transformação inteira num único job
   server-side.

Por isso o notebook só monta a string SQL e dispara `client.query(...)`; não
há pandas na transformação (só numa célula de preview, no fim, para inspeção
visual).

### Tipagem explícita (RF-005)

- `nr_assentos_ofertados`: `SAFE_CAST(... AS INT64)`.
- As quatro colunas de horário (`dt_partida_prevista`, `dt_partida_real`,
  `dt_chegada_prevista`, `dt_chegada_real`): `SAFE.PARSE_DATETIME('%d/%m/%Y
  %H:%M', ...)`. Esse formato foi conferido em amostras de vários arquivos
  (2023 e 2024) e é o único observado nessas quatro colunas — diferente de
  `dt_referencia`, abaixo.
- `dt_referencia`: aqui a fonte tem **dois formatos**, na mesma linha da
  divisão do `Codeshare` — `AAAA-MM-DD` nos arquivos mais antigos e
  `DD/MM/AAAA HH:MM:SS` nos mais novos. A query tenta os dois com
  `COALESCE(SAFE.PARSE_DATE('%Y-%m-%d', ...), SAFE.PARSE_DATE('%d/%m/%Y',
  SUBSTR(..., 1, 10)))`. Sem isso, metade dos arquivos teria `dt_referencia`
  nula — e como é a chave de partição, a tabela inteira ficaria mal
  particionada silenciosamente.
- Todo `PARSE_*` usa a variante `SAFE.`, e não a função direta: campos vazios
  (comuns em `dt_partida_real`/`dt_chegada_real`, por voos ainda não
  realizados ou cancelados) não podem estourar o job inteiro — viram `NULL`.

### Dedup (RF-006)

```sql
ROW_NUMBER() OVER (
  PARTITION BY sg_empresa_icao, nr_voo, dt_referencia, sg_icao_origem, dt_partida_prevista
  ORDER BY _ingested_at DESC
) AS rn
...
QUALIFY rn = 1
```

A chave escolhida (companhia + número do voo + data de referência +
aeroporto de origem + partida prevista) é a identidade natural de uma perna
de voo — não existe uma chave primária explícita nos dados. Em caso de
empate, fica o registro com `_ingested_at` mais recente: hoje há um único
lote, então isso não muda nada, mas passa a importar quando a Bronze for
reingerida em T2/TF e a mesma janela de datas for carregada de novo.

### Filtros (RF-007, RF-008, RF-008b)

- `WHERE ds_situacao_voo = 'REALIZADO'` — aplicado já na CTE `tipado`, antes
  do dedup e do cálculo de atraso.
- `dt_partida_prevista IS NOT NULL AND dt_partida_real IS NOT NULL` — RF-008b,
  descarta os registros sem o par completo (o PRD mede isso em 6,4% da base
  da API; não conferimos esse percentual na base CSV, pode diferir).
- `ABS(DATETIME_DIFF(dt_partida_real, dt_partida_prevista, MINUTE)) <= 1440`
  — RF-008. O PRD **não fixa um valor exato** para "faixa plausível", só cita
  os extremos observados na API (−1.453 min e +3.894 min) como exemplo de
  erro de virada de data. Confirmado com você: usar **±1440 min (±24h)** —
  esse corte exclui exatamente os dois extremos citados e preserva a
  população legítima de voos "Antecipado" (atraso negativo, ~52% da base
  segundo o PRD §10.2, não é outlier).

### Cálculo do atraso (RF-009)

```sql
DATETIME_DIFF(dt_partida_real, dt_partida_prevista, MINUTE) AS atraso_partida_minutos
```

`DATETIME_DIFF`, não `TIMESTAMP_DIFF` — `PARSE_DATETIME` produz `DATETIME`
(sem timezone), já que a fonte não traz timezone explícito. Usar
`TIMESTAMP_DIFF` aqui daria erro de tipo.

### Particionamento e clusterização (RNF-008)

`PARTITION BY dt_referencia` — já definida no PRD §10.2 como "chave de
particionamento" para os dados do VRA. `CLUSTER BY sg_empresa_icao,
sg_icao_origem` — companhia e aeroporto de origem são os filtros mais
prováveis em análises de atraso por rota/companhia; diferente da Bronze,
aqui dá pra clusterizar porque a Silver é tabela nativa (external table não
aceita `CLUSTER BY` no BigQuery).

### Linhagem preservada

`_ingested_at`, `_batch_id` e `_source_uri` (via `_FILE_NAME AS
_source_uri`) são propagados da Bronze para a Silver sem alteração — mesmo
não sendo mencionados no RF-005 a RF-009, manter a linhagem completa até a
Silver custa nada e evita perder rastreabilidade numa camada intermediária.
`ds_codeshare`, a coluna extra descoberta na Bronze, também é propagada
(sem tipagem adicional — é só um indicador textual).

### Validação

A última célula compara `num_rows` da Bronze com o da Silver e imprime o
percentual de queda. O PRD (§10.1) trata essa queda como esperada e como
evidência de que a Silver fez trabalho real (filtro de `REALIZADO`, remoção
de pares incompletos e de outliers) — por isso está no roteiro de
demonstração, não é um sinal de erro.

---

## Coisas que ficaram em aberto

- **PRD §10.2 não menciona `Codeshare` nem o formato duplo de
  `dt_referencia`** — o dicionário foi verificado contra a API, não contra
  os CSVs que efetivamente usamos. Vale registrar essa divergência de fonte
  quando o grupo revisar aquela seção; não fiz essa edição sozinho.
- **RF-008b cita 6,4% de pares incompletos, medido na API** — não conferimos
  se esse percentual se sustenta na base CSV real; a célula de validação da
  Silver mostra a queda total, mas não decompõe por motivo (filtro
  `REALIZADO` vs. par incompleto vs. outlier). Se for útil para a
  apresentação, dá pra adicionar essa quebra.
- **Nenhum dos dois notebooks foi executado por mim** contra o projeto real
  — as duas tabelas foram criadas rodando os notebooks no Colab. Este
  documento descreve o que o código faz, não uma execução verificada aqui.
