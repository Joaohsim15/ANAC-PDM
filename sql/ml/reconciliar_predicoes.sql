SELECT
  COUNT(*) AS total_predicoes,
  COUNTIF(p.nr_voo IS NOT NULL AND p.dt_referencia IS NOT NULL AND p.dt_partida_prevista IS NOT NULL) AS com_chave,
  COUNT(g.atrasou) AS reconciliadas
FROM `${PROJECT_ID}.tf_anac.tb_anac_predicoes_log` AS p
LEFT JOIN `${PROJECT_ID}.tf_anac.tb_anac_gold_features_atraso` AS g
  ON g.sg_empresa_icao = p.sg_empresa_icao
  AND g.nr_voo = p.nr_voo
  AND g.dt_referencia = p.dt_referencia
  AND g.dt_partida_prevista = p.dt_partida_prevista;

-- ------------------- 2. Acuracia em producao (so as reconciliadas) ---------
WITH reconciliado AS (
  SELECT
    p.prob_atraso,
    IF(p.prob_atraso >= 0.5, 1, 0) AS previsto,
    g.atrasou AS real
  FROM `${PROJECT_ID}.tf_anac.tb_anac_predicoes_log` AS p
  JOIN `${PROJECT_ID}.tf_anac.tb_anac_gold_features_atraso` AS g
    ON g.sg_empresa_icao = p.sg_empresa_icao
    AND g.nr_voo = p.nr_voo
    AND g.dt_referencia = p.dt_referencia
    AND g.dt_partida_prevista = p.dt_partida_prevista
)
SELECT
  COUNT(*)                                          AS n,
  ROUND(AVG(IF(previsto = real, 1, 0)), 4)          AS acuracia_em_producao,
  ROUND(AVG(IF(real = 1, 1, 0)), 4)                 AS taxa_real_de_atraso,
  SUM(IF(previsto = 1 AND real = 1, 1, 0))          AS verdadeiro_positivo,
  SUM(IF(previsto = 1 AND real = 0, 1, 0))          AS falso_positivo,
  SUM(IF(previsto = 0 AND real = 1, 1, 0))          AS falso_negativo,
  SUM(IF(previsto = 0 AND real = 0, 1, 0))          AS verdadeiro_negativo
FROM reconciliado;
