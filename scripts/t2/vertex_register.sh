#!/usr/bin/env bash
# Registra o M1 do BigQuery ML no Vertex AI Model Registry. Idempotente.
# Usa o modelo vigente no BigQuery (nao o artefato exportado no GCS, que pode
# ser de um treino anterior). So acrescenta metadado: nao retreina nada.
source "$(dirname "$0")/_env.sh"

log "registrando ${DATASET}.mdl_anac_m1_boosted_tree como ${VERTEX_MODEL_ID}"
bq query --project_id="${PROJECT_ID}" --nouse_legacy_sql \
  "ALTER MODEL \`${PROJECT_ID}.${DATASET}.mdl_anac_m1_boosted_tree\`
   SET OPTIONS (vertex_ai_model_id = '${VERTEX_MODEL_ID}')"

gcloud ai models describe "${VERTEX_MODEL_ID}" --project "${PROJECT_ID}" --region "${REGION}" \
  --format="table(displayName, versionId, versionAliases.list(), modelSourceInfo.sourceType)"
