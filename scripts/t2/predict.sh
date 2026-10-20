#!/usr/bin/env bash
# Chamada da demo a API do Cloud Run (privada: token de identidade do gcloud).
#   ./predict.sh             -> voo valido com clima, devolve a probabilidade
#   ./predict.sh --sem-clima -> mesmo voo sem os campos de clima (aerodromo sem estacao)
#   ./predict.sh --explain   -> contribuicao de cada feature para a previsao
#   ./predict.sh --invalido  -> payload fora do contrato, devolve 422
#   ./predict.sh --health
# Referencia do ML.PREDICT no BigQuery para este voo: 0,6136 com clima e
# 0,6026 sem clima. A API deve devolver o mesmo valor.
source "$(dirname "$0")/_env.sh"

URL="$(gcloud run services describe "${API_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" \
  --format='value(status.url)')"
TOKEN="$(gcloud auth print-identity-token)"

VOO_SEM_CLIMA='{
  "sg_empresa_icao": "GLO", "sg_icao_origem": "SBGO", "sg_icao_destino": "SBGR",
  "cd_tipo_linha": "N", "sg_equipamento_icao": "B738",
  "dia_semana": "6", "mes": "12",
  "nr_assentos_ofertados": 186, "hora_partida_prevista": 18, "duracao_prevista_min": 75
}'
# fim de tarde de dezembro em Goiania com trovoada (TS) no METAR
VOO='{
  "sg_empresa_icao": "GLO", "sg_icao_origem": "SBGO", "sg_icao_destino": "SBGR",
  "cd_tipo_linha": "N", "sg_equipamento_icao": "B738",
  "dia_semana": "6", "mes": "12",
  "nr_assentos_ofertados": 186, "hora_partida_prevista": 18, "duracao_prevista_min": 75,
  "clima_temperatura_c": 27.0, "clima_umidade_relativa_pct": 74.0,
  "clima_velocidade_vento_kmh": 14.8, "clima_rajada_vento_kmh": null,
  "clima_visibilidade_m": 9999.0, "clima_pressao_hpa": 1012.0,
  "clima_cobertura_nuvens": "SCT", "clima_altura_nuvens_m": 900.0,
  "clima_fenomenos": "TS"
}'

case "${1:-}" in
  --health)
    curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer ${TOKEN}" "${URL}/health" ;;
  --sem-clima)
    curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      -d "${VOO_SEM_CLIMA}" "${URL}/predict" ;;
  --explain)
    # consulta o BigQuery direto (nao o Vertex): leva 1 a 3 s
    curl -sS -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      -d "${VOO}" "${URL}/explain" ;;
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
