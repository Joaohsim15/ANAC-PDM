CREATE OR REPLACE TABLE `${PROJECT_ID}.tf_anac.tb_anac_silver_metar`
PARTITION BY DATE(dt_observacao_utc)
CLUSTER BY sg_icao
AS
WITH tipado AS (
  SELECT
    station AS sg_icao,
    -- "valid" ja vem em UTC porque o download pede tz=UTC (scripts/baixar_metar.py)
    SAFE.PARSE_DATETIME('%Y-%m-%d %H:%M', valid) AS dt_observacao_utc,
    SAFE_CAST(NULLIF(tmpf, 'null') AS FLOAT64) AS nr_temperatura_f,
    SAFE_CAST(NULLIF(dwpf, 'null') AS FLOAT64) AS nr_ponto_orvalho_f,
    SAFE_CAST(NULLIF(relh, 'null') AS FLOAT64) AS nr_umidade_relativa_pct,
    SAFE_CAST(NULLIF(drct, 'null') AS FLOAT64) AS nr_direcao_vento_graus,
    SAFE_CAST(NULLIF(sknt, 'null') AS FLOAT64) AS nr_velocidade_vento_nos,
    SAFE_CAST(NULLIF(gust, 'null') AS FLOAT64) AS nr_rajada_vento_nos,
    SAFE_CAST(NULLIF(vsby, 'null') AS FLOAT64) AS nr_visibilidade_milhas,
    -- mslp (pressao ao nivel do mar) nao e reportada fora dos EUA: 0 de
    -- 6.471.426 linhas preenchidas no backfill (confirmado em 18/10/2026) —
    -- nao entra na Silver. alti (altimetro/QNH) e o campo de pressao real
    -- usado, preenchido em 99,2% das observacoes
    SAFE_CAST(NULLIF(alti, 'null') AS FLOAT64) AS nr_altimetro_inhg,
    skyc1 AS ds_cobertura_nuvens_1,
    SAFE_CAST(NULLIF(skyl1, 'null') AS FLOAT64) AS nr_altura_nuvens_1_pes,
    NULLIF(wxcodes, 'null') AS ds_fenomenos,
    NULLIF(metar, 'null') AS ds_metar_bruto,
    _ingested_at,
    _batch_id,
    _FILE_NAME AS _source_uri
  FROM `${PROJECT_ID}.tf_anac.tb_anac_metar_bronze`
),
deduplicado AS (
  -- a IEM pode reenviar a mesma observacao se o backfill for rodado de novo;
  -- mantem a ingestao mais recente de cada (estacao, horario)
  SELECT *
  FROM tipado
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY sg_icao, dt_observacao_utc
    ORDER BY _ingested_at DESC
  ) = 1
)
SELECT
  sg_icao,
  dt_observacao_utc,
  -- unidades convertidas para metrico (regra do schemas/features.json quando
  -- estas colunas entrarem no contrato, no Estagio 4 do plano de implementacao)
  (nr_temperatura_f - 32) / 1.8 AS nr_temperatura_c,
  (nr_ponto_orvalho_f - 32) / 1.8 AS nr_ponto_orvalho_c,
  nr_umidade_relativa_pct,
  nr_direcao_vento_graus,
  nr_velocidade_vento_nos * 1.852 AS nr_velocidade_vento_kmh,
  nr_rajada_vento_nos * 1.852 AS nr_rajada_vento_kmh,
  nr_visibilidade_milhas * 1609.34 AS nr_visibilidade_m,
  -- 0,17% dos valores de alti sao fisicamente implausiveis (ex.: alti=0.38,
  -- 2.98 — garbage da fonte, a IEM avisa que ha pouco controle de
  -- qualidade); fora de 850-1100 hPa (mesmo limite do contrato em
  -- schemas/features.json, clima_pressao_hpa) trata como ausente em vez de
  -- propagar lixo pro treino
  IF(nr_altimetro_inhg * 33.8639 BETWEEN 850 AND 1100,
     nr_altimetro_inhg * 33.8639, NULL) AS nr_altimetro_hpa,
  ds_cobertura_nuvens_1,
  nr_altura_nuvens_1_pes * 0.3048 AS nr_altura_nuvens_1_m,
  ds_fenomenos,
  ds_metar_bruto,
  _ingested_at,
  _batch_id,
  _source_uri
FROM deduplicado
WHERE dt_observacao_utc IS NOT NULL;
