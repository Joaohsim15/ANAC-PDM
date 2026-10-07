#!/usr/bin/env bash
# LIGA o endpoint: implanta o M1 (cobrado por hora enquanto implantado).
# Rodar 2 dias antes da demo e desligar logo depois com vertex_undeploy.sh.
source "$(dirname "$0")/_env.sh"

ENDPOINT_ID="$(endpoint_id)"
if [[ -z "${ENDPOINT_ID}" ]]; then
  log "criando endpoint ${VERTEX_ENDPOINT_NAME} (vazio nao gera custo)"
  gcloud ai endpoints create --project "${PROJECT_ID}" --region "${REGION}" \
    --display-name "${VERTEX_ENDPOINT_NAME}"
  ENDPOINT_ID="$(endpoint_id)"
fi

DEPLOYED="$(gcloud ai endpoints describe "${ENDPOINT_ID}" --project "${PROJECT_ID}" --region "${REGION}" \
  --format="value(deployedModels[].id)")"
if [[ -n "${DEPLOYED}" ]]; then
  log "endpoint ${ENDPOINT_ID} ja tem modelo implantado (${DEPLOYED}); nada a fazer"
  exit 0
fi

log "implantando ${VERTEX_MODEL_ID} em ${ENDPOINT_ID} (${VERTEX_MACHINE_TYPE}, 1 replica; leva ~15 min)"
gcloud ai endpoints deploy-model "${ENDPOINT_ID}" --project "${PROJECT_ID}" --region "${REGION}" \
  --model "${VERTEX_MODEL_ID}" --display-name "anac-m1" \
  --machine-type "${VERTEX_MACHINE_TYPE}" --min-replica-count 1 --max-replica-count 1 \
  --traffic-split 0=100

log "pronto. VERTEX_ENDPOINT_ID=${ENDPOINT_ID}"
