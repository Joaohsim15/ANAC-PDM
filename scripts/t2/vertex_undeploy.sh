#!/usr/bin/env bash
# DESLIGA o endpoint: desimplanta todos os modelos. O endpoint vazio fica
# (nao gera custo) e o proximo vertex_deploy.sh reaproveita o mesmo id.
source "$(dirname "$0")/_env.sh"

ENDPOINT_ID="$(endpoint_id)"
if [[ -z "${ENDPOINT_ID}" ]]; then
  log "endpoint ${VERTEX_ENDPOINT_NAME} nao existe; nada a desligar"
  exit 0
fi

for DEPLOYED_ID in $(gcloud ai endpoints describe "${ENDPOINT_ID}" --project "${PROJECT_ID}" \
  --region "${REGION}" --format="value(deployedModels[].id)" | tr ';' ' '); do
  log "desimplantando ${DEPLOYED_ID} de ${ENDPOINT_ID}"
  gcloud ai endpoints undeploy-model "${ENDPOINT_ID}" --project "${PROJECT_ID}" --region "${REGION}" \
    --deployed-model-id "${DEPLOYED_ID}"
done
log "endpoint ${ENDPOINT_ID} sem modelos: custo por hora zerado"
