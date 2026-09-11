-- ============================================================================
-- BigQuery ML - Avaliacao de M1 e do baseline no split temporal
-- Origem  : tf_anac.vw_anac_gold_avaliacao_m1 (is_eval = TRUE, ultimos 60 dias)
-- ============================================================================

-- ---------------------------------------------- 1. Placar comparado --------
SELECT
'baseline - LOGISTIC_REG'  AS modelo,
ROUND(roc_auc,   4)        AS auc_roc,
ROUND(precision, 4)        AS precisao,
ROUND(recall,    4)        AS revocacao,
ROUND(f1_score,  4)        AS f1,
ROUND(accuracy,  4)        AS acuracia
FROM ML.EVALUATE(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_baseline_logreg`,
TABLE `pdm-bia-2026.tf_anac.vw_anac_gold_avaliacao_m1`,
STRUCT(0.5 AS threshold)
)
UNION ALL
SELECT
'M1 - BOOSTED_TREE',
ROUND(roc_auc,   4),
ROUND(precision, 4),
ROUND(recall,    4),
ROUND(f1_score,  4),
ROUND(accuracy,  4)
FROM ML.EVALUATE(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
TABLE `pdm-bia-2026.tf_anac.vw_anac_gold_avaliacao_m1`,
STRUCT(0.5 AS threshold)
)
ORDER BY auc_roc DESC;

-- ------------------------------------- 2. Matriz de confusao de M1 --------
SELECT *
FROM ML.CONFUSION_MATRIX(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
TABLE `pdm-bia-2026.tf_anac.vw_anac_gold_avaliacao_m1`,
STRUCT(0.5 AS threshold)
);

-- ------------------------------------------------ 3. Curva ROC ------------
SELECT
ROUND(threshold,           3) AS limiar,
ROUND(recall,              4) AS revocacao,
ROUND(false_positive_rate, 4) AS taxa_falso_positivo,
true_positives, false_positives, true_negatives, false_negatives
FROM ML.ROC_CURVE(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
TABLE `pdm-bia-2026.tf_anac.vw_anac_gold_avaliacao_m1`,
GENERATE_ARRAY(0.0, 1.0, 0.05)
)
ORDER BY limiar;

-- ------------------------------ 4. Importancia global das features --------
SELECT feature, ROUND(attribution, 5) AS atribuicao
FROM ML.GLOBAL_EXPLAIN(MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`)
ORDER BY atribuicao DESC;

-- --------------------- 5. Ganho de M1 sobre o baseline --------
WITH m1 AS (
SELECT roc_auc FROM ML.EVALUATE(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`,
TABLE `pdm-bia-2026.tf_anac.vw_anac_gold_avaliacao_m1`)
),
bl AS (
SELECT roc_auc FROM ML.EVALUATE(
MODEL `pdm-bia-2026.tf_anac.mdl_anac_baseline_logreg`,
TABLE `pdm-bia-2026.tf_anac.vw_anac_gold_avaliacao_m1`)
)
SELECT
ROUND(m1.roc_auc, 4)              AS auc_m1,
ROUND(bl.roc_auc, 4)              AS auc_baseline,
ROUND(m1.roc_auc - bl.roc_auc, 4) AS ganho,
m1.roc_auc >= 0.70                AS atingiu_alvo_auc,
(m1.roc_auc - bl.roc_auc) >= 0.02 AS atingiu_alvo_ganho
FROM m1, bl;