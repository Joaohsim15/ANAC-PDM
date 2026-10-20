-- ============================================================================
-- BigQuery ML - M1: classificador binario de atraso de partida (> 15 min)
-- Origem  : tf_anac.vw_anac_gold_treino_m1_clima
-- Destino : tf_anac.mdl_anac_m1_boosted_tree
--
-- Promovido em 18/10/2026 com as features de meteorologia (METAR/IEM, ver
-- docs/PRD.md P-09): validado lado a lado em sql/ml/model_m1_boosted_tree_clima.sql
-- contra o M1 sem clima no mesmo split temporal (AUC 0,6532 vs 0,6527, ganho
-- de +0,0005 — marginal, mas atingiu o criterio >= definido). GLOBAL_EXPLAIN
-- mostrou sinal real em clima_fenomenos (6a feature mais importante); as
-- demais features de clima contribuem pouco. Decisao de promover mesmo com
-- ganho pequeno foi do grupo, nao automatica.
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
ENABLE_GLOBAL_EXPLAIN     = TRUE,
-- o M1 e servido pelo Vertex AI; depois do primeiro registro, o BigQuery
-- recusa recriar o modelo sem estas opcoes. Retreinar cria nova versao.
MODEL_REGISTRY            = 'VERTEX_AI',
VERTEX_AI_MODEL_ID        = 'anac_m1_boosted_tree'
) AS
SELECT
-- as 10 features originais do contrato + as 9 de clima + alvo binario
sg_empresa_icao, sg_icao_origem, sg_icao_destino, cd_tipo_linha,
sg_equipamento_icao, dia_semana, mes,
nr_assentos_ofertados, hora_partida_prevista, duracao_prevista_min,
clima_temperatura_c, clima_umidade_relativa_pct, clima_velocidade_vento_kmh,
clima_rajada_vento_kmh, clima_visibilidade_m, clima_pressao_hpa,
clima_cobertura_nuvens, clima_altura_nuvens_m, clima_fenomenos,
atrasou
FROM `pdm-bia-2026.tf_anac.vw_anac_gold_treino_m1_clima`;