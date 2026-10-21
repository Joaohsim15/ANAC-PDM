#!/usr/bin/env bash
# LIGA o pipeline de streaming de METAR no Dataflow (cobrado por hora ligado).
# Desligar ao fim de cada teste/demo com dataflow_drain_metar.sh.
# Devolve o terminal assim que o job e submetido; ele leva ~4 min ate processar.
source "$(dirname "$0")/_env.sh"

if [[ -n "$(metar_active_job_id)" ]]; then
  log "job ${METAR_DATAFLOW_JOB} ja esta ativo; nada a fazer"
  exit 0
fi

# array vazio + set -u quebra no bash 3.2 (padrao do macOS): expandir com ${SA_FLAG[@]+...}
SA_FLAG=()
[[ -n "${DATAFLOW_SERVICE_ACCOUNT}" ]] && SA_FLAG=(--service_account_email "${DATAFLOW_SERVICE_ACCOUNT}")

cd "${ROOT_DIR}/streaming/dataflow" || exit 1
log "lancando ${METAR_DATAFLOW_JOB} em ${REGION}"
uv run --no-project --python 3.12 --with-requirements requirements.txt \
  python -m pipeline.run \
  --domain metar \
  --input_subscription "projects/${PROJECT_ID}/subscriptions/${METAR_SUBSCRIPTION}" \
  --output_table "${PROJECT_ID}:${DATASET}.${METAR_STREAM_TABLE}" \
  --dead_letter_topic "projects/${PROJECT_ID}/topics/${METAR_DLQ_TOPIC}" \
  --contract "${ROOT_DIR}/schemas/features.json" \
  --runner DataflowRunner \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --job_name "${METAR_DATAFLOW_JOB}" \
  --temp_location "gs://${DATAFLOW_BUCKET}/temp" \
  --staging_location "gs://${DATAFLOW_BUCKET}/staging" \
  --setup_file ./setup.py \
  --machine_type e2-standard-2 --num_workers 1 --max_num_workers 2 \
  --enable_streaming_engine \
  --no_wait_until_finish \
  --labels projeto=anac-pdm --labels entrega=t2 --labels dominio=metar \
  ${SA_FLAG[@]+"${SA_FLAG[@]}"}

log "acompanhe em https://console.cloud.google.com/dataflow/jobs?project=${PROJECT_ID}"
