# shellcheck shell=bash
# Carregado pelos demais scripts: le o .env da raiz e valida as variaveis.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

: "${PROJECT_ID:?defina PROJECT_ID no .env (modelo em .env.example)}"
# as bibliotecas Python cobram a cota do quota_project das credenciais ADC, que
# pode ser outro projeto do usuario; fixa o projeto do trabalho
export GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" GOOGLE_CLOUD_QUOTA_PROJECT="${PROJECT_ID}"
export CLOUDSDK_CORE_PROJECT="${PROJECT_ID}"
REGION="${REGION:-us-central1}"
DATASET="${DATASET:-tf_anac}"
VERTEX_MODEL_ID="${VERTEX_MODEL_ID:-anac_m1_boosted_tree}"
VERTEX_ENDPOINT_NAME="${VERTEX_ENDPOINT_NAME:-anac-atraso-endpoint}"
VERTEX_MACHINE_TYPE="${VERTEX_MACHINE_TYPE:-n1-standard-2}"
API_SERVICE="${API_SERVICE:-anac-api}"
API_SERVICE_ACCOUNT="${API_SERVICE_ACCOUNT:-}"
TOPIC="${TOPIC:-anac-voos}"
DLQ_TOPIC="${DLQ_TOPIC:-anac-voos-dlq}"
SUBSCRIPTION="${SUBSCRIPTION:-anac-voos-dataflow}"
DATAFLOW_JOB="${DATAFLOW_JOB:-anac-stream-eventos}"
DATAFLOW_SERVICE_ACCOUNT="${DATAFLOW_SERVICE_ACCOUNT:-}"
DATAFLOW_BUCKET="${DATAFLOW_BUCKET:-${PROJECT_ID}-anac-dataflow}"
export IMAGE_REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/anac"

log() { printf '\033[1;34m[t2]\033[0m %s\n' "$*"; }

# id numerico do endpoint pelo nome de exibicao (vazio se nao existir)
endpoint_id() {
  gcloud ai endpoints list --project "${PROJECT_ID}" --region "${REGION}" \
    --filter="displayName=${VERTEX_ENDPOINT_NAME}" --format="value(name.basename())" 2>/dev/null | head -n1
}

# id do job Dataflow ativo pelo nome (vazio se nao houver)
active_job_id() {
  gcloud dataflow jobs list --project "${PROJECT_ID}" --region "${REGION}" --status=active \
    --filter="name=${DATAFLOW_JOB}" --format="value(id)" 2>/dev/null | head -n1
}
