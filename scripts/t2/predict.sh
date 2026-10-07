#!/usr/bin/env bash
# Chamada da demo a API do Cloud Run (privada: token de identidade do gcloud).
#   ./predict.sh             -> voo valido, devolve a probabilidade
#   ./predict.sh --invalido  -> payload fora do contrato, devolve 422
#   ./predict.sh --health
source "$(dirname "$0")/_env.sh"

URL="$(gcloud run services describe "${API_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" \
  --format='value(status.url)')"
TOKEN="$(gcloud auth print-identity-token)"

VOO='{
  "sg_empresa_icao": "GLO", "sg_icao_origem": "SBGO", "sg_icao_destino": "SBGR",
  "cd_tipo_linha": "N", "sg_equipamento_icao": "B738",
  "dia_semana": "6", "mes": "12",
  "nr_assentos_ofertados": 186, "hora_partida_prevista": 18, "duracao_prevista_min": 75
}'

case "${1:-}" in
  --health)
    curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer ${TOKEN}" "${URL}/health" ;;
  --invalido)
    # mes com zero a esquerda e campo pos-partida: os dois violam o contrato
    INVALIDO='{
      "sg_empresa_icao": "GLO", "sg_icao_origem": "SBGO", "sg_icao_destino": "SBGR",
      "cd_tipo_linha": "N", "sg_equipamento_icao": "B738",
      "dia_semana": "6", "mes": "012",
      "nr_assentos_ofertados": 186, "hora_partida_prevista": 18, "duracao_prevista_min": 75,
      "ds_situacao_partida": "Atraso 30-60"
    }'
    curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      -d "${INVALIDO}" "${URL}/predict" ;;
  *)
    curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      -d "${VOO}" "${URL}/predict" ;;
esac
