-- Cria a camada Silver do VRA a partir da Bronze: tipagem explícita
-- (RF-005), dedup via QUALIFY ROW_NUMBER() (RF-006), filtro de voos
-- REALIZADO (RF-007), descarte de pares incompletos e de outliers
-- (RF-008/RF-008b) e cálculo do atraso de partida em minutos (RF-009).
--
-- Cópia literal da SQL executada por `client.query(sql_silver)` em
-- bronze_to_silver_vra.ipynb — só os nomes de tabela já vêm resolvidos
-- (o notebook monta a mesma string via f-string com PROJECT_ID/DATASET_ID).
--
-- Decisões que valem uma nota (detalhe completo em docs/bronze_silver.md):
--   - dt_referencia tem dois formatos na fonte (AAAA-MM-DD nos arquivos
--     mais antigos, DD/MM/AAAA HH:MM:SS nos mais novos — mesma leva que
--     trouxe a coluna Codeshare na Bronze). Daí o COALESCE de dois
--     SAFE.PARSE_DATE.
--   - Faixa plausível de atraso (RF-008) fixada em ±1440 min (±24h) —
--     confirmado com o grupo; o PRD só cita os extremos observados como
--     exemplo, sem fixar um corte.
--   - PARTITION BY dt_referencia: já definida no PRD §10.2 como chave de
--     particionamento. CLUSTER BY só é possível aqui porque a Silver é
--     tabela nativa — a Bronze, external table, não aceita CLUSTER BY.
CREATE OR REPLACE TABLE `pdm-bia-2026.tf_anac.tb_anac_silver`
PARTITION BY dt_referencia
CLUSTER BY sg_empresa_icao, sg_icao_origem
AS
WITH tipado AS (
  SELECT
    sg_empresa_icao,
    nm_empresa,
    nr_voo,
    cd_di,
    cd_tipo_linha,
    sg_equipamento_icao,
    SAFE_CAST(nr_assentos_ofertados AS INT64) AS nr_assentos_ofertados,
    sg_icao_origem,
    nm_aerodromo_origem,
    SAFE.PARSE_DATETIME('%d/%m/%Y %H:%M', dt_partida_prevista) AS dt_partida_prevista,
    SAFE.PARSE_DATETIME('%d/%m/%Y %H:%M', dt_partida_real)     AS dt_partida_real,
    sg_icao_destino,
    nm_aerodromo_destino,
    SAFE.PARSE_DATETIME('%d/%m/%Y %H:%M', dt_chegada_prevista) AS dt_chegada_prevista,
    SAFE.PARSE_DATETIME('%d/%m/%Y %H:%M', dt_chegada_real)     AS dt_chegada_real,
    ds_situacao_voo,
    NULLIF(ds_justificativa, '') AS ds_justificativa,
    COALESCE(
      SAFE.PARSE_DATE('%Y-%m-%d', dt_referencia),
      SAFE.PARSE_DATE('%d/%m/%Y', SUBSTR(dt_referencia, 1, 10))
    ) AS dt_referencia,
    ds_situacao_partida,
    ds_situacao_chegada,
    ds_codeshare,
    _ingested_at,
    _batch_id,
    _FILE_NAME AS _source_uri
  FROM `pdm-bia-2026.tf_anac.tb_vra_bronze`
  WHERE ds_situacao_voo = 'REALIZADO'
),
deduplicado AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY sg_empresa_icao, nr_voo, dt_referencia, sg_icao_origem, dt_partida_prevista
      ORDER BY _ingested_at DESC
    ) AS rn
  FROM tipado
  QUALIFY rn = 1
)
SELECT
  * EXCEPT(rn),
  DATETIME_DIFF(dt_partida_real, dt_partida_prevista, MINUTE) AS atraso_partida_minutos
FROM deduplicado
WHERE
  dt_partida_prevista IS NOT NULL
  AND dt_partida_real IS NOT NULL
  AND ABS(DATETIME_DIFF(dt_partida_real, dt_partida_prevista, MINUTE)) <= 1440;
