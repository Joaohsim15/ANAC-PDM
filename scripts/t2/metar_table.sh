#!/usr/bin/env bash
# Cria a tabela de destino do streaming de METAR a partir do DDL versionado.
# Idempotente.
source "$(dirname "$0")/_env.sh"

log "criando ${DATASET}.${METAR_STREAM_TABLE} (se nao existir)"
PROJECT_ID="${PROJECT_ID}" envsubst '${PROJECT_ID}' \
  < "${ROOT_DIR}/sql/streaming/create_table_stream_metar.sql" \
  | bq query --project_id="${PROJECT_ID}" --nouse_legacy_sql
