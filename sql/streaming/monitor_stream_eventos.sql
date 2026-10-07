-- ============================================================================
-- Streaming - consulta da demo: eventos chegando no BigQuery
-- Varre so a particao de hoje (filtro em event_ts).
-- ============================================================================

SELECT
  COUNT(*)                                             AS eventos_hoje,
  COUNT(DISTINCT simulation_run_id)                    AS execucoes_simulador,
  MAX(ingest_ts)                                       AS ultimo_ingest,
  ROUND(AVG(TIMESTAMP_DIFF(ingest_ts, publish_ts, MILLISECOND)) / 1000, 2) AS lag_medio_s,
  ROUND(MAX(TIMESTAMP_DIFF(ingest_ts, publish_ts, MILLISECOND)) / 1000, 2) AS lag_max_s
FROM `${PROJECT_ID}.tf_anac.tb_anac_stream_eventos`
WHERE DATE(event_ts) = CURRENT_DATE();

-- Ultimos eventos recebidos
SELECT
  ingest_ts,
  sg_empresa_icao,
  nr_voo,
  CONCAT(sg_icao_origem, ' -> ', sg_icao_destino) AS rota,
  dt_partida_prevista,
  sg_equipamento_icao
FROM `${PROJECT_ID}.tf_anac.tb_anac_stream_eventos`
WHERE DATE(event_ts) = CURRENT_DATE()
ORDER BY ingest_ts DESC
LIMIT 10;
