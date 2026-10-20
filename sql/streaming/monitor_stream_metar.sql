-- ============================================================================
-- Streaming - consulta da demo: observacoes de METAR chegando no BigQuery
-- Varre so a particao de hoje (filtro em event_ts).
-- ============================================================================

SELECT
  COUNT(*)                                             AS observacoes_hoje,
  COUNT(DISTINCT sg_icao)                              AS estacoes,
  COUNT(DISTINCT simulation_run_id)                    AS execucoes_simulador,
  MAX(ingest_ts)                                       AS ultimo_ingest,
  ROUND(AVG(TIMESTAMP_DIFF(ingest_ts, publish_ts, MILLISECOND)) / 1000, 2) AS lag_medio_s,
  ROUND(MAX(TIMESTAMP_DIFF(ingest_ts, publish_ts, MILLISECOND)) / 1000, 2) AS lag_max_s
FROM `${PROJECT_ID}.tf_anac.tb_anac_stream_metar`
WHERE DATE(event_ts) = CURRENT_DATE();

-- Ultimas observacoes recebidas
SELECT
  ingest_ts,
  sg_icao,
  dt_observacao_utc,
  ROUND(clima_temperatura_c, 1)          AS temperatura_c,
  ROUND(clima_velocidade_vento_kmh, 1)   AS vento_kmh,
  ROUND(clima_visibilidade_m)            AS visibilidade_m,
  clima_cobertura_nuvens,
  clima_fenomenos
FROM `${PROJECT_ID}.tf_anac.tb_anac_stream_metar`
WHERE DATE(event_ts) = CURRENT_DATE()
ORDER BY ingest_ts DESC
LIMIT 10;
