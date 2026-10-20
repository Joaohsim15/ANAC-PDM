"""Simulador de eventos de METAR: rele o historico e republica no Pub/Sub.

Le observacoes meteorologicas reais da Silver no BigQuery (nunca a IEM ao
vivo), desloca o horario da observacao para o presente e publica um evento
por observacao, no ritmo pedido. Mesmo padrao de streaming/producer/simulator.py
(voo), mas e quem agora cumpre o requisito de streaming do T2: meteorologia
em streaming, voos em batch (Medallion do T1, inalterado).

Uso:
    python -m simulator_metar --project $PROJECT --topic anac-metar \\
        --data-observacao 2024-12-20 --limite 300 --por-segundo 5
"""

import argparse
import json
import logging
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "schemas" / "features.json"

logger = logging.getLogger("anac-metar-simulator")

# nome da coluna na Silver de METAR -> nome da feature no contrato
# (schemas/features.json usa o prefixo clima_, a Silver usa o padrao nr_/ds_
# do resto do repo — ver sql/silver/create_table_silver_metar.sql)
SILVER_PARA_CONTRATO = {
    "nr_temperatura_c": "clima_temperatura_c",
    "nr_umidade_relativa_pct": "clima_umidade_relativa_pct",
    "nr_velocidade_vento_kmh": "clima_velocidade_vento_kmh",
    "nr_rajada_vento_kmh": "clima_rajada_vento_kmh",
    "nr_visibilidade_m": "clima_visibilidade_m",
    "nr_altimetro_hpa": "clima_pressao_hpa",
    "ds_cobertura_nuvens_1": "clima_cobertura_nuvens",
    "nr_altura_nuvens_1_m": "clima_altura_nuvens_m",
    "ds_fenomenos": "clima_fenomenos",
}
CONTRATO_PARA_SILVER = {feat: col for col, feat in SILVER_PARA_CONTRATO.items()}


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def metar_feature_specs(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Features deste simulador: so as de clima (nullable no contrato).

    Espelha flight_feature_specs() do simulador de voo, do lado contrario —
    aqui so interessam as 9 features de meteorologia.
    """
    return [spec for spec in contract["features"] if spec.get("nullable")]


def load_feature_names(path: Path = CONTRACT_PATH) -> list[str]:
    return [spec["name"] for spec in metar_feature_specs(load_contract(path))]


def contract_filters(contract: dict[str, Any]) -> list[str]:
    """Condicoes SQL equivalentes ao contrato, sobre as colunas da Silver.

    Ao contrario do simulador de voo, aqui ausencia e um valor legitimo
    (estacao sem aquele sensor numa observacao, ou aerodromo sem estacao
    meteorologica): o filtro so recusa valor PREENCHIDO fora do
    dominio/faixa do contrato, nunca a ausencia.
    """
    conditions = []
    for spec in metar_feature_specs(contract):
        col = CONTRATO_PARA_SILVER[spec["name"]]
        if "pattern" in spec:
            conditions.append(f"({col} IS NULL OR REGEXP_CONTAINS({col}, r'{spec['pattern']}'))")
        if "enum" in spec:
            values = ", ".join(f"'{v}'" for v in spec["enum"])
            conditions.append(f"({col} IS NULL OR {col} IN ({values}))")
        if "minimum" in spec:
            conditions.append(f"({col} IS NULL OR {col} >= {spec['minimum']})")
        if "maximum" in spec:
            conditions.append(f"({col} IS NULL OR {col} <= {spec['maximum']})")
    return conditions


def build_query(project: str, contract: dict[str, Any]) -> str:
    colunas_features = [f"{CONTRATO_PARA_SILVER[spec['name']]} AS {spec['name']}" for spec in metar_feature_specs(contract)]
    # colunas enumeradas a partir do contrato; nunca SELECT *
    columns = ",\n  ".join(["sg_icao", "dt_observacao_utc", *colunas_features])
    filters = "\n  AND ".join(["DATE(dt_observacao_utc) = @data_observacao", *contract_filters(contract)])
    return f"""
SELECT
  {columns}
FROM `{project}.tf_anac.tb_anac_silver_metar`
WHERE {filters}
ORDER BY dt_observacao_utc
LIMIT @limite
"""


def shift_observation(original: datetime, offset: timedelta) -> datetime:
    return original + offset


def to_event(row: dict[str, Any], feature_names: list[str], offset: timedelta, run_id: str, now: datetime) -> dict[str, Any]:
    original = row["dt_observacao_utc"]
    event = {name: row[name] for name in feature_names}
    event.update(
        {
            "event_id": str(uuid.uuid4()),
            "event_ts": now.astimezone(timezone.utc).isoformat(),
            "sg_icao": row.get("sg_icao"),
            "dt_observacao_utc": shift_observation(original, offset).isoformat(),
            "dt_observacao_original": original.isoformat(),
            "simulation_run_id": run_id,
        }
    )
    return event


def observation_offset(reference_day: date, today: date) -> timedelta:
    """Desloca o dia de referencia inteiro para hoje, mantendo a hora da observacao.

    Mesma logica de departure_offset() do simulador de voo: so o dia muda, a
    hora da observacao permanece a do historico.
    """
    return datetime.combine(today, datetime.min.time()) - datetime.combine(reference_day, datetime.min.time())


def fetch_rows(project: str, reference_day: date, limit: int, contract: dict[str, Any]) -> list[dict[str, Any]]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    job = client.query(
        build_query(project, contract),
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("data_observacao", "DATE", reference_day),
                bigquery.ScalarQueryParameter("limite", "INT64", limit),
            ]
        ),
    )
    rows = [dict(r.items()) for r in job.result()]
    # a Silver e a fonte; se ela nao devolveu o esperado, nao publica parcial calado
    if not rows:
        raise RuntimeError(f"nenhuma observacao de METAR na Silver para {reference_day}")
    return rows


def publish(
    events: Iterable[dict[str, Any]],
    project: str,
    topic: str,
    per_second: float,
) -> int:
    from google.cloud import pubsub_v1

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project, topic)
    interval = 1.0 / per_second if per_second > 0 else 0.0
    futures = []
    for i, event in enumerate(events, start=1):
        futures.append(publisher.publish(topic_path, json.dumps(event).encode("utf-8")))
        if i % 25 == 0:
            logger.info("%d eventos publicados", i)
        if interval:
            time.sleep(interval)
    # confirma cada publicacao: falha aqui e erro, nao silencio
    for future in futures:
        future.result(timeout=60)
    return len(futures)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True)
    parser.add_argument("--topic", default="anac-metar")
    parser.add_argument("--data-observacao", type=date.fromisoformat, default=date(2024, 12, 20),
                        help="dia do historico a reler (AAAA-MM-DD, UTC)")
    parser.add_argument("--limite", type=int, default=300, help="maximo de observacoes publicadas")
    parser.add_argument("--por-segundo", type=float, default=5.0, help="ritmo de publicacao (0 = sem pausa)")
    parser.add_argument("--dry-run", action="store_true", help="imprime os eventos em vez de publicar")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    contract = load_contract()
    feature_names = [spec["name"] for spec in metar_feature_specs(contract)]
    rows = fetch_rows(args.project, args.data_observacao, args.limite, contract)
    now = datetime.now(timezone.utc)
    offset = observation_offset(args.data_observacao, now.date())
    run_id = f"sim-metar-{now:%Y%m%dT%H%M%S}"
    events = [to_event(r, feature_names, offset, run_id, now) for r in rows]
    logger.info("run_id=%s observacoes=%d data_observacao=%s", run_id, len(events), args.data_observacao)

    if args.dry_run:
        for event in events[:5]:
            print(json.dumps(event, ensure_ascii=False))
        return 0
    sent = publish(events, args.project, args.topic, args.por_segundo)
    logger.info("concluido: %d eventos publicados em %s", sent, args.topic)
    return 0


if __name__ == "__main__":
    sys.exit(main())
