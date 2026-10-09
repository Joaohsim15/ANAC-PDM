-- ============================================================================
-- BigQuery ML - M1: classificador binario de atraso de partida (> 15 min)
-- Origem  : tf_anac.vw_anac_gold_treino_m1
-- Destino : tf_anac.mdl_anac_m1_boosted_tree
-- ============================================================================

CREATE OR REPLACE MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`
OPTIONS (
MODEL_TYPE                = 'BOOSTED_TREE_CLASSIFIER',
BOOSTER_TYPE              = 'GBTREE',
TREE_METHOD               = 'HIST',
INPUT_LABEL_COLS          = ['atrasou'],
AUTO_CLASS_WEIGHTS        = TRUE,
CATEGORY_ENCODING_METHOD  = 'LABEL_ENCODING',
DATA_SPLIT_METHOD         = 'RANDOM',
DATA_SPLIT_EVAL_FRACTION  = 0.10,
MAX_ITERATIONS            = 50,
LEARN_RATE                = 0.1,
MAX_TREE_DEPTH            = 8,
SUBSAMPLE                 = 0.8,
COLSAMPLE_BYTREE          = 0.8,
MIN_TREE_CHILD_WEIGHT     = 10,
L2_REG                    = 1.0,
EARLY_STOP                = TRUE,
MIN_REL_PROGRESS          = 0.005,
ENABLE_GLOBAL_EXPLAIN     = TRUE
) AS
SELECT
-- as 10 features do contrato + alvo binario
sg_empresa_icao, sg_icao_origem, sg_icao_destino, cd_tipo_linha,
sg_equipamento_icao, dia_semana, mes,
nr_assentos_ofertados, hora_partida_prevista, duracao_prevista_min,
atrasou
FROM `pdm-bia-2026.tf_anac.vw_anac_gold_treino_m1`;