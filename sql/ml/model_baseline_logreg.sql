-- ============================================================================
-- BigQuery ML - BASELINE: regressao logistica sobre o alvo binario
-- Origem  : tf_anac.vw_anac_gold_treino_m1
-- Destino : tf_anac.mdl_anac_baseline_logreg
-- ============================================================================

CREATE OR REPLACE MODEL `pdm-bia-2026.tf_anac.mdl_anac_baseline_logreg`
OPTIONS (
MODEL_TYPE               = 'LOGISTIC_REG',
INPUT_LABEL_COLS         = ['atrasou'],
AUTO_CLASS_WEIGHTS       = TRUE,
DATA_SPLIT_METHOD        = 'RANDOM',
DATA_SPLIT_EVAL_FRACTION = 0.10,
L2_REG                   = 0.1,
MAX_ITERATIONS           = 20,
EARLY_STOP               = TRUE
) AS
SELECT
-- as 10 features do contrato + alvo binario
sg_empresa_icao, sg_icao_origem, sg_icao_destino, cd_tipo_linha,
sg_equipamento_icao, dia_semana, mes,
nr_assentos_ofertados, hora_partida_prevista, duracao_prevista_min,
atrasou
FROM `pdm-bia-2026.tf_anac.vw_anac_gold_treino_m1`;