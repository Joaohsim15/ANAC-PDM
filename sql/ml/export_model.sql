-- ============================================================================
-- BigQuery ML - EXPORT MODEL: ponte validada para o Trabalho 2
-- Destino : gs://dados-anac-vra/models/
-- ----------------------------------------------------------------------------
-- BOOSTED_TREE sai em formato XGBoost Booster; LOGISTIC_REG sai em SavedModel
-- do TensorFlow. Ambos aceitos pelo Vertex AI Model Registry no T2.
-- ============================================================================

EXPORT MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`
OPTIONS (URI = 'gs://dados-anac-vra/models/m1_boosted_tree/');

EXPORT MODEL `pdm-bia-2026.tf_anac.mdl_anac_baseline_logreg`
OPTIONS (URI = 'gs://dados-anac-vra/models/baseline_logreg/');