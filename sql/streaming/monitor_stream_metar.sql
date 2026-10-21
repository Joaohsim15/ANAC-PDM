-- ============================================================================
-- Streaming - consulta da demo: observacoes de METAR chegando no BigQuery
-- Olha so os ultimos 15 min de processamento (ingest_ts, carimbado pelo
-- Dataflow). O filtro em event_ts limita a varredura as particoes de ontem a
-- amanha, o que cobre uma mensagem publicada a mao com outra data.
-- ============================================================================

SELECT
  COUNT(*)                                             AS observacoes_15min,
  COUNT(DISTINCT sg_icao)                              AS estacoes,
  COUNT(DISTINCT simulation_run_id)                    AS execucoes_simulador,
  MAX(ingest_ts)                                       AS ultimo_ingest,
  ROUND(AVG(TIMESTAMP_DIFF(ingest_ts, publish_ts, MILLISECOND)) / 1000, 2) AS lag_medio_s,
  ROUND(MAX(TIMESTAMP_DIFF(ingest_ts, publish_ts, MILLISECOND)) / 1000, 2) AS lag_max_s
FROM `${PROJECT_ID}.tf_anac.tb_anac_stream_metar`
WHERE DATE(event_ts) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) AND DATE_ADD(CURRENT_DATE(), INTERVAL 1 DAY)
  AND ingest_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 MINUTE);

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
WHERE DATE(event_ts) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) AND DATE_ADD(CURRENT_DATE(), INTERVAL 1 DAY)
  AND ingest_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 MINUTE)
ORDER BY ingest_ts DESC
LIMIT 10;
