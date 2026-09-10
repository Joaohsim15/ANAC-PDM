-- ============================================================================
-- BigQuery ML - M1: classificador binario de atraso de partida (> 15 min)
-- Origem  : tf_anac.vw_anac_gold_treino_m1
-- Destino : tf_anac.mdl_anac_m1_boosted_tree
-- Atende  : RF-015, RF-017, RF-018 - Aceite A1.8, A1.9, A1.10
-- ----------------------------------------------------------------------------
-- Por que BOOSTED_TREE_CLASSIFIER e nao DNN ou AutoML:
--   1. Exporta em formato XGBoost Booster, que o EXPORT MODEL do T2 exige
--      (RF-017 / R-02). Validar isso ainda no T1 e deliberado.
--   2. ML.EXPLAIN_PREDICT usa Tree SHAP - explicabilidade nativa, sem custo
--      extra de infraestrutura (RF-018).
--   3. Lida bem com categorica de alta cardinalidade (175 aeroportos de origem)
--      sob LABEL_ENCODING, sem estourar a matriz esparsa do one-hot.
--
-- ATENCAO DE CUSTO E TEMPO: BOOSTED_TREE treina no backend do Vertex AI, fora
-- do free tier de consulta do BigQuery (secao 12.3). Tempo MEDIDO: ~40 min
-- sobre 2,47 mi de linhas. Rodar UMA vez, na vespera - jamais ao vivo.
-- Se o credito apertar, restringir a view de treino a dt_referencia >=
-- '2024-01-01' derruba o custo sem mudar a narrativa.
--
-- Resultado medido em 10/09/2026, sobre is_eval, limiar 0,5:
--   AUC-ROC 0,6584 - precisao 0,3147 - revocacao 0,7459 - F1 0,4426
--   Baseline (41): AUC 0,6417. Ganho de 0,0167.
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
SELECT * FROM `pdm-bia-2026.tf_anac.vw_anac_gold_treino_m1`;