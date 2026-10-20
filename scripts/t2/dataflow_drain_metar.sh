#!/usr/bin/env bash
# DESLIGA o pipeline de METAR: drain processa o que ja chegou e encerra sem perder eventos.
source "$(dirname "$0")/_env.sh"

JOB_ID="$(metar_active_job_id)"
if [[ -z "${JOB_ID}" ]]; then
  log "nenhum job ${METAR_DATAFLOW_JOB} ativo; nada a desligar"
  exit 0
fi
log "drain do job ${JOB_ID}"
gcloud dataflow jobs drain "${JOB_ID}" --project "${PROJECT_ID}" --region "${REGION}"
