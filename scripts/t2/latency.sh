#!/usr/bin/env bash
# Mede a latencia de POST /predict pela internet (inclui rede e Vertex).
#   ./latency.sh        -> 50 chamadas sequenciais, imprime p50/p95/max
#   ./latency.sh 100
source "$(dirname "$0")/_env.sh"

N="${1:-50}"
URL="$(gcloud run services describe "${API_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" \
  --format='value(status.url)')"
TOKEN="$(gcloud auth print-identity-token)"
VOO='{"sg_empresa_icao":"GLO","sg_icao_origem":"SBGO","sg_icao_destino":"SBGR","cd_tipo_linha":"N","sg_equipamento_icao":"B738","dia_semana":"6","mes":"12","nr_assentos_ofertados":186,"hora_partida_prevista":18,"duracao_prevista_min":75}'

log "aquecendo e medindo ${N} chamadas em ${URL}/predict"
curl -sS -o /dev/null -H "Authorization: Bearer ${TOKEN}" "${URL}/health"

TIMES="$(mktemp)"
FAILS=0
for _ in $(seq "${N}"); do
  OUT="$(curl -sS -o /dev/null -w '%{http_code} %{time_total}' -H "Authorization: Bearer ${TOKEN}" \
    -H 'Content-Type: application/json' -d "${VOO}" "${URL}/predict")"
  if [[ "${OUT%% *}" == "200" ]]; then echo "${OUT#* }" >> "${TIMES}"; else FAILS=$((FAILS + 1)); fi
done

LC_ALL=C sort -n "${TIMES}" | LC_ALL=C awk -v fails="${FAILS}" '
  { t[NR] = $1 * 1000 }
  END {
    if (NR == 0) { print "nenhuma chamada com sucesso"; exit 1 }
    p50 = t[int(NR * 0.50 + 0.5)]; p95 = t[int(NR * 0.95 + 0.5)]
    printf "ok=%d falhas=%d  p50=%.0f ms  p95=%.0f ms  max=%.0f ms  (meta p95 <= 800 ms)\n", NR, fails, p50, p95, t[NR]
  }'
rm -f "${TIMES}"
