#!/usr/bin/env bash
# Build da imagem (Cloud Build) e deploy da API no Cloud Run, privada.
#   ./api_deploy.sh            -> min-instances=0 (escala a zero, custo ~0)
#   ./api_deploy.sh --demo     -> min-instances=1 (sem cold start na apresentacao)
source "$(dirname "$0")/_env.sh"

MIN_INSTANCES=0
[[ "${1:-}" == "--demo" ]] && MIN_INSTANCES=1

ENDPOINT_ID="$(endpoint_id)"
: "${ENDPOINT_ID:?endpoint ${VERTEX_ENDPOINT_NAME} nao encontrado; rode vertex_deploy.sh}"

TAG="$(git -C "${ROOT_DIR}" rev-parse --short HEAD)"
IMAGE="${IMAGE_REPO}/${API_SERVICE}:${TAG}"

log "build ${IMAGE}"
# cloudbuild.yaml aponta o Dockerfile da API com a raiz do repo como contexto
gcloud builds submit "${ROOT_DIR}" --project "${PROJECT_ID}" --region "${REGION}" \
  --config "${ROOT_DIR}/api/cloudbuild.yaml" --substitutions "_IMAGE=${IMAGE}"

SA_FLAG=()
[[ -n "${API_SERVICE_ACCOUNT}" ]] && SA_FLAG=(--service-account "${API_SERVICE_ACCOUNT}")

log "deploy ${API_SERVICE} (min-instances=${MIN_INSTANCES}, sem acesso publico)"
gcloud run deploy "${API_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" \
  --image "${IMAGE}" "${SA_FLAG[@]}" \
  --no-allow-unauthenticated \
  --min-instances "${MIN_INSTANCES}" --max-instances 3 \
  --cpu 1 --memory 512Mi --concurrency 20 --timeout 30 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},VERTEX_REGION=${REGION},VERTEX_ENDPOINT_ID=${ENDPOINT_ID}" \
  --labels "projeto=anac-pdm,entrega=t2"

gcloud run services describe "${API_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" \
  --format="value(status.url)"
