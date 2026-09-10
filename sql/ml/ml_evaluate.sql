-- ============================================================================
-- BigQuery ML - Avaliacao de M1 e do baseline no split temporal
-- Origem  : tf_anac.vw_anac_gold_avaliacao_m1 (is_eval = TRUE, ultimos 60 dias)
-- Atende  : RF-016 - Aceite A1.8 - metricas-alvo da secao 9.1
-- ----------------------------------------------------------------------------
-- Os dois modelos sao avaliados sobre EXATAMENTE o mesmo conjunto, que nenhum
-- dos dois viu no treino. O split e temporal, nao aleatorio: prever o passado
-- com dado do futuro e o modo mais comum de inflar metrica em serie temporal.
-- Custo: leitura de ~151 mil linhas. Segundos, centavos.
--
-- Rodar UM BLOCO POR VEZ: selecione o trecho e Ctrl+Enter.
-- ============================================================================

-- ---------------------------------------------- 1. Placar comparado --------
-- A query da apresentacao: uma linha por modelo, ordenada por AUC.
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
-- Os limiares sao passados EXPLICITAMENTE. Sem o terceiro argumento o
-- ML.ROC_CURVE devolve um limiar por probabilidade distinta observada -
-- dezenas de milhares de linhas com valores arbitrarios que nenhum filtro
-- redondo acerta. Pedir a grade e o que garante que a query devolva o grafico.
--
-- E o slide que justifica a saida em probabilidade: o analista escolhe onde
-- ficar na curva conforme a folga do turno (secao 4.2).
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
-- Medido em 10/09/2026: hora_partida_prevista 0,062 domina, sozinha vale mais
-- que empresa + origem + destino somados. E o efeito cascata da secao 3.1
-- aparecendo no modelo - QUANDO o voo parte importa mais que QUEM opera.
SELECT feature, ROUND(attribution, 5) AS atribuicao
FROM ML.GLOBAL_EXPLAIN(MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`)
ORDER BY atribuicao DESC;

-- --------------------- 5. Ganho de M1 sobre o baseline (secao 9.1) --------
-- Alvos: AUC >= 0,70 e ganho >= 0,02. Medido em 10/09/2026: 0,6584 e 0,0167.
-- Os dois ficaram de fora, e isso vai nos slides como ACHADO, com hipotese de
-- causa: as 10 features descrevem so a PROGRAMACAO do voo, nada sobre o estado
-- do dia (meteorologia, rotacao da aeronave, atraso acumulado da malha).
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