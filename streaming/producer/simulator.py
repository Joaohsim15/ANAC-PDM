"""Simulador de eventos de voo: rele o historico e republica no Pub/Sub.

Le voos reais da Gold no BigQuery (nunca a API ou o site da ANAC), desloca a
partida prevista para o presente e publica um evento por voo, no ritmo pedido.
So entram campos conhecidos antes da decolagem; horario real, situacao e
justificativa nunca saem daqui.

Uso:
    python -m simulator --project $PROJECT --topic anac-voos \\
        --data-referencia 2024-12-20 --limite 300 --por-segundo 5
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

logger = logging.getLogger("anac-simulator")


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_feature_names(path: Path = CONTRACT_PATH) -> list[str]:
    return [spec["name"] for spec in load_contract(path)["features"]]


def contract_filters(contract: dict[str, Any]) -> list[str]:
    """Condicoes SQL equivalentes ao contrato.

    O historico tem ~0,03% de linhas sujas (assentos negativos, equipamento
    nulo). Elas seriam recusadas pelo pipeline; o simulador nem as publica,
    para a demo nao depender do dead-letter disparar por acaso.
    """
    conditions = []
    for spec in contract["features"]:
        name = spec["name"]
        conditions.append(f"{name} IS NOT NULL")
        if "pattern" in spec:
            conditions.append(f"REGEXP_CONTAINS({name}, r'{spec['pattern']}')")
        if "enum" in spec:
            values = ", ".join(f"'{v}'" for v in spec["enum"])
            conditions.append(f"{name} IN ({values})")
        if "minimum" in spec:
            conditions.append(f"{name} >= {spec['minimum']}")
        if "maximum" in spec:
            conditions.append(f"{name} <= {spec['maximum']}")
    return conditions


def build_query(project: str, contract: dict[str, Any]) -> str:
    feature_names = [spec["name"] for spec in contract["features"]]
    # colunas enumeradas a partir do contrato; nunca SELECT *
    columns = ",\n  ".join(["nr_voo", "dt_partida_prevista", *feature_names])
    filters = "\n  AND ".join(["dt_referencia = @data_referencia", *contract_filters(contract)])
    return f"""
SELECT
  {columns}
FROM `{project}.tf_anac.tb_anac_gold_features_atraso`
WHERE {filters}
ORDER BY dt_partida_prevista
LIMIT @limite
"""


def shift_departure(original: datetime, offset: timedelta) -> datetime:
    return original + offset


def to_event(row: dict[str, Any], feature_names: list[str], offset: timedelta, run_id: str, now: datetime) -> dict[str, Any]:
    original = row["dt_partida_prevista"]
    event = {name: row[name] for name in feature_names}
    event.update(
        {
            "event_id": str(uuid.uuid4()),
            "event_ts": now.astimezone(timezone.utc).isoformat(),
            "nr_voo": row.get("nr_voo"),
            "dt_partida_prevista": shift_departure(original, offset).isoformat(),
            "dt_partida_prevista_original": original.isoformat(),
            "simulation_run_id": run_id,
        }
    )
    return event


def departure_offset(reference_day: date, today: date) -> timedelta:
    """Desloca o dia de referencia inteiro para hoje, mantendo a hora do voo.

    As features dia_semana, mes e hora continuam as do historico: o modelo
    precisa ver o voo como ele foi programado, nao a data da demo.
    """
    return datetime.combine(today, datetime.min.time()) - datetime.combine(reference_day, datetime.min.time())


def fetch_rows(project: str, reference_day: date, limit: int, contract: dict[str, Any]) -> list[dict[str, Any]]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    job = client.query(
        build_query(project, contract),
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("data_referencia", "DATE", reference_day),
                bigquery.ScalarQueryParameter("limite", "INT64", limit),
            ]
        ),
    )
    rows = [dict(r.items()) for r in job.result()]
    # a Gold e a fonte; se ela nao devolveu o esperado, nao publica parcial calado
    if not rows:
        raise RuntimeError(f"nenhum voo na Gold para {reference_day}")
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
    parser.add_argument("--topic", default="anac-voos")
    parser.add_argument("--data-referencia", type=date.fromisoformat, default=date(2024, 12, 20),
                        help="dia do historico a reler (AAAA-MM-DD)")
    parser.add_argument("--limite", type=int, default=300, help="maximo de voos publicados")
    parser.add_argument("--por-segundo", type=float, default=5.0, help="ritmo de publicacao (0 = sem pausa)")
    parser.add_argument("--dry-run", action="store_true", help="imprime os eventos em vez de publicar")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    contract = load_contract()
    feature_names = [spec["name"] for spec in contract["features"]]
    rows = fetch_rows(args.project, args.data_referencia, args.limite, contract)
    now = datetime.now(timezone.utc)
    offset = departure_offset(args.data_referencia, now.date())
    run_id = f"sim-{now:%Y%m%dT%H%M%S}"
    events = [to_event(r, feature_names, offset, run_id, now) for r in rows]
    logger.info("run_id=%s voos=%d data_referencia=%s", run_id, len(events), args.data_referencia)

    if args.dry_run:
        for event in events[:5]:
            print(json.dumps(event, ensure_ascii=False))
        return 0
    sent = publish(events, args.project, args.topic, args.por_segundo)
    logger.info("concluido: %d eventos publicados em %s", sent, args.topic)
    return 0


if __name__ == "__main__":
    sys.exit(main())
