-- ============================================================================
-- BigQuery ML - EXPORT MODEL: ponte validada para o Trabalho 2
-- Destino : gs://dados-anac-vra/models/
-- Atende  : RF-017 - Aceite A1.9 - risco R-02
-- ----------------------------------------------------------------------------
-- Validar o EXPORT ainda no T1 e deliberado. Descobrir em outubro que o tipo de
-- modelo escolhido nao exporta inviabilizaria o T2 inteiro (R-02) - e outubro
-- seria tarde para trocar de modelo. Aqui custa uma query de segundos.
--
-- BOOSTED_TREE sai em formato XGBoost Booster; LOGISTIC_REG sai em SavedModel
-- do TensorFlow. Ambos aceitos pelo Vertex AI Model Registry no T2.
--
-- EXECUTADO COM SUCESSO em 10/09/2026, 22 s para os dois. R-02 ENCERRADO.
-- Executar na vespera, junto com o CREATE MODEL - nunca ao vivo.
-- ============================================================================

EXPORT MODEL `pdm-bia-2026.tf_anac.mdl_anac_m1_boosted_tree`
OPTIONS (URI = 'gs://dados-anac-vra/models/m1_boosted_tree/');

EXPORT MODEL `pdm-bia-2026.tf_anac.mdl_anac_baseline_logreg`
OPTIONS (URI = 'gs://dados-anac-vra/models/baseline_logreg/');

-- Conferencia (rodar no Cloud Shell, nao aqui):
--   gcloud storage ls -r gs://dados-anac-vra/models/