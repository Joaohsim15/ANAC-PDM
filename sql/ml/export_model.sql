-- ============================================================================
-- BigQuery ML - EXPORT MODEL: ponte validada para o Trabalho 2
-- Destino : gs://${GCS_BUCKET}/models/
-- ----------------------------------------------------------------------------
-- BOOSTED_TREE sai em formato XGBoost Booster; LOGISTIC_REG sai em SavedModel
-- do TensorFlow. Ambos aceitos pelo Vertex AI Model Registry no T2.
-- ============================================================================

EXPORT MODEL `${PROJECT_ID}.tf_anac.mdl_anac_m1_boosted_tree`
OPTIONS (URI = 'gs://${GCS_BUCKET}/models/m1_boosted_tree/');

EXPORT MODEL `${PROJECT_ID}.tf_anac.mdl_anac_baseline_logreg`
OPTIONS (URI = 'gs://${GCS_BUCKET}/models/baseline_logreg/');