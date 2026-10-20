#!/usr/bin/env bash
# Publica observacoes de METAR no Pub/Sub relendo o historico da Silver.
#   ./simulate_metar.sh                      -> 300 observacoes de 2024-12-20, 5/s
#   ./simulate_metar.sh --limite 50 --por-segundo 10
#   ./simulate_metar.sh --invalido           -> 1 evento fora do contrato (demo do dead-letter)
source "$(dirname "$0")/_env.sh"

if [[ "${1:-}" == "--invalido" ]]; then
  log "publicando evento com valor fora do contrato (deve ir para ${METAR_DLQ_TOPIC})"
  gcloud pubsub topics publish "${METAR_TOPIC}" --project "${PROJECT_ID}" \
    --message '{"event_id":"demo-metar-invalido","event_ts":"2026-10-23T14:00:00Z","sg_icao":"SBGO","clima_cobertura_nuvens":"XXX"}'
  exit 0
fi

cd "${ROOT_DIR}/streaming/producer" || exit 1
uv run --no-project --python 3.12 --with-requirements requirements.txt \
  python simulator_metar.py --project "${PROJECT_ID}" --topic "${METAR_TOPIC}" "$@"
