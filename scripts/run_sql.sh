#!/usr/bin/env bash
# Roda um SQL versionado no BigQuery, trocando ${PROJECT_ID} e ${GCS_BUCKET}
# pelos valores do .env (padroes em scripts/t2/_env.sh).
#   ./scripts/run_sql.sh sql/gold/gold_features_atraso.sql
#   ./scripts/run_sql.sh sql/ml/ml_evaluate.sql --dry_run    # valida sem custo
source "$(dirname "$0")/t2/_env.sh"

SQL_FILE="${1:?uso: run_sql.sh <arquivo.sql> [--dry_run]}"
shift

log "rodando ${SQL_FILE} em ${PROJECT_ID}"
# lista explicita: so essas duas variaveis sao trocadas, nada mais no SQL
envsubst '${PROJECT_ID} ${GCS_BUCKET}' < "${SQL_FILE}" \
  | bq query --project_id="${PROJECT_ID}" --nouse_legacy_sql "$@"
