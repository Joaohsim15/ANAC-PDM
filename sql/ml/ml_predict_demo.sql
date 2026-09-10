-- ============================================================================
-- BigQuery ML - Predicao e explicabilidade
-- ============================================================================

-- ------------------------ 1. Um voo inventado na hora -------------
WITH voo_inventado AS (
SELECT
'GLO'  AS sg_empresa_icao,      -- GOL
'SBGO' AS sg_icao_origem,       -- Goiania
'SBGR' AS sg_icao_destino,      -- Guarulhos
'N'    AS cd_tipo_linha,        -- nacional
'B738' AS sg_equipamento_icao,  -- 737-800
186    AS nr_assentos_ofertados,
EXTRACT(HOUR FROM partida_prevista)                       AS hora_partida_prevista,
CAST(EXTRACT(DAYOFWEEK FROM partida_prevista) AS STRING)  AS dia_semana,
CAST(EXTRACT(MONTH     FROM partida_prevista) AS STRING)  AS mes,
DATETIME_DIFF(chegada_prevista, partida_prevista, MINUTE) AS duracao_prevista_min
FROM (
SELECT
DATETIME '2024-12-20 18:30:00' AS partida_prevista,
DATETIME '2024-12-20 19:45:00' AS chegada_prevista
)
),
predicao AS (
SELECT
predicted_atrasou,
(SELECT p.prob FROM UNNEST(predicted_atrasou_probs) AS p
WHERE CAST(p.label AS STRING) = '1') AS prob_atraso
FROM ML.PREDICT(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
TABLE voo_inventado
)
)
SELECT
predicted_atrasou     AS predicao,
ROUND(prob_atraso, 4) AS prob_atraso,
CASE
WHEN prob_atraso >= 0.60 THEN 'RISCO ALTO'   -- 17% dos voos; acima de 0,70 cai para <1%
WHEN prob_atraso >= 0.50 THEN 'RISCO MEDIO'
ELSE                          'RISCO BAIXO'
END                   AS faixa_de_risco
FROM predicao;

-- ------------------ 2. Por que? SHAP nativo ----------
WITH voo_inventado AS (
SELECT
'GLO' AS sg_empresa_icao, 'SBGO' AS sg_icao_origem, 'SBGR' AS sg_icao_destino,
'N'   AS cd_tipo_linha,   'B738' AS sg_equipamento_icao,
186   AS nr_assentos_ofertados,
18    AS hora_partida_prevista,
'6'   AS dia_semana,      '12'   AS mes,
75    AS duracao_prevista_min
)
SELECT
ROUND(prediction_value, 5)       AS score_bruto,
atribuicao.feature               AS atributo,
ROUND(atribuicao.attribution, 5) AS empurrao
FROM ML.EXPLAIN_PREDICT(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
TABLE voo_inventado,
STRUCT(3 AS top_k_features)
), UNNEST(top_feature_attributions) AS atribuicao
ORDER BY ABS(empurrao) DESC;

-- --------------- 3. Ranking operacional do dia ------
SELECT
sg_empresa_icao,
nr_voo,
CONCAT(sg_icao_origem, ' -> ', sg_icao_destino) AS rota,
dt_partida_prevista,
ROUND((SELECT p.prob FROM UNNEST(predicted_atrasou_probs) AS p
WHERE CAST(p.label AS STRING) = '1'), 4)        AS prob_atraso,
atrasou                                         AS atrasou_de_fato,
atraso_partida_minutos                          AS atraso_real_min
FROM ML.PREDICT(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
(
SELECT
-- as 10 features do contrato
sg_empresa_icao, sg_icao_origem, sg_icao_destino, cd_tipo_linha,
sg_equipamento_icao, dia_semana, mes,
nr_assentos_ofertados, hora_partida_prevista, duracao_prevista_min,
-- carona para exibicao (ignoradas pelo modelo)
nr_voo, dt_partida_prevista, atrasou, atraso_partida_minutos
FROM `pdm-bia-2026.tf_anac.tb_anac_gold_features_atraso`
WHERE dt_referencia = DATE '2024-12-20'
)
)
ORDER BY prob_atraso DESC
LIMIT 15;