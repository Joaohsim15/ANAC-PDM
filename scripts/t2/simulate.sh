#!/usr/bin/env bash
# Publica eventos de voo no Pub/Sub relendo o historico da Gold.
#   ./simulate.sh                      -> 300 voos de 2024-12-20, 5 por segundo
#   ./simulate.sh --limite 50 --por-segundo 10
#   ./simulate.sh --invalido           -> 1 evento fora do contrato (demo do dead-letter)
source "$(dirname "$0")/_env.sh"

if [[ "${1:-}" == "--invalido" ]]; then
  log "publicando evento com campo pos-partida (deve ir para ${DLQ_TOPIC})"
  gcloud pubsub topics publish "${TOPIC}" --project "${PROJECT_ID}" \
    --message '{"event_id":"demo-invalido","event_ts":"2026-10-23T14:00:00Z","sg_empresa_icao":"GLO","ds_situacao_partida":"Atraso 30-60"}'
  exit 0
fi

cd "${ROOT_DIR}/streaming/producer" || exit 1
uv run --no-project --python 3.12 --with-requirements requirements.txt \
  python simulator.py --project "${PROJECT_ID}" --topic "${TOPIC}" "$@"
