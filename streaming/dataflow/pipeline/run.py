"""Pipeline Beam: Pub/Sub -> validacao -> BigQuery, com dead-letter.

Serve dois dominios (--domain), que so diferem nos metadados do evento e no
recorte de features do contrato que validam - ver pipeline/transforms.py:
  - voo (padrao): streaming/producer/simulator.py -> tb_anac_stream_eventos
  - metar: streaming/producer/simulator_metar.py -> tb_anac_stream_metar

Uso (Dataflow, voo):
    python -m pipeline.run \\
        --input_subscription projects/$PROJECT/subscriptions/anac-voos-dataflow \\
        --output_table $PROJECT:tf_anac.tb_anac_stream_eventos \\
        --dead_letter_topic projects/$PROJECT/topics/anac-voos-dlq \\
        --runner DataflowRunner --project $PROJECT --region us-central1 \\
        --temp_location gs://$BUCKET/temp --streaming

Uso (Dataflow, metar):
    python -m pipeline.run --domain metar \\
        --input_subscription projects/$PROJECT/subscriptions/anac-metar-dataflow \\
        --output_table $PROJECT:tf_anac.tb_anac_stream_metar \\
        --dead_letter_topic projects/$PROJECT/topics/anac-metar-dlq \\
        --runner DataflowRunner --project $PROJECT --region us-central1 \\
        --temp_location gs://$BUCKET/temp --streaming
"""

import argparse
import json
import logging
from pathlib import Path

import apache_beam as beam
from apache_beam.io.gcp.bigquery import BigQueryDisposition, WriteToBigQuery
from apache_beam.io.gcp.bigquery_tools import RetryStrategy
from apache_beam.io.gcp.pubsub import ReadFromPubSub, WriteToPubSub
from apache_beam.metrics import Metrics
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions, StandardOptions

from pipeline.transforms import (
    EVENT_FIELDS,
    METAR_EVENT_FIELDS,
    METAR_REQUIRED_EVENT_FIELDS,
    REQUIRED_EVENT_FIELDS,
    InvalidEvent,
    dead_letter_record,
    metar_feature_names,
    parse_event,
)

DEAD_LETTER = "dead_letter"
# lido no lancamento e serializado junto com o DoFn: os workers nao leem arquivo
CONTRACT_PATH = Path(__file__).resolve().parents[3] / "schemas" / "features.json"

# feature_names=None (dominio voo) valida todas as features do contrato; o
# dominio metar resolve o proprio recorte em runtime via metar_feature_names,
# ja que depende do contrato carregado (ver main())
DOMAINS = {
    "voo": {"event_fields": EVENT_FIELDS, "required_event_fields": REQUIRED_EVENT_FIELDS, "feature_names": None},
    "metar": {"event_fields": METAR_EVENT_FIELDS, "required_event_fields": METAR_REQUIRED_EVENT_FIELDS},
}


class ParseEvent(beam.DoFn):
    """Valida cada mensagem; as invalidas saem pela tag de dead-letter."""

    def __init__(
        self,
        contract: dict,
        event_fields: dict[str, str] = EVENT_FIELDS,
        required_event_fields: tuple[str, ...] = REQUIRED_EVENT_FIELDS,
        feature_names: set[str] | None = None,
    ) -> None:
        self._contract = contract
        self._event_fields = event_fields
        self._required_event_fields = required_event_fields
        self._feature_names = feature_names
        self._valid = Metrics.counter("anac", "eventos_validos")
        self._invalid = Metrics.counter("anac", "eventos_dead_letter")

    def process(self, message):
        try:
            row = parse_event(
                message.data,
                self._contract,
                publish_ts=message.publish_time,
                event_fields=self._event_fields,
                required_event_fields=self._required_event_fields,
                feature_names=self._feature_names,
            )
        except InvalidEvent as exc:
            self._invalid.inc()
            logging.warning("evento invalido: %s", exc)
            yield beam.pvalue.TaggedOutput(DEAD_LETTER, dead_letter_record(message.data, str(exc)))
            return
        self._valid.inc()
        yield row


def bigquery_schema(
    contract: dict,
    event_fields: dict[str, str] = EVENT_FIELDS,
    feature_names: set[str] | None = None,
) -> dict:
    fields = [
        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_ts", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "publish_ts", "type": "TIMESTAMP", "mode": "NULLABLE"},
        {"name": "ingest_ts", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
    fields += [
        {"name": name, "type": bq_type, "mode": "NULLABLE"}
        for name, bq_type in event_fields.items()
        if name not in ("event_id", "event_ts")
    ]
    selected_features = (
        contract["features"] if feature_names is None else [s for s in contract["features"] if s["name"] in feature_names]
    )
    fields += [
        {"name": s["name"], "type": s["type"], "mode": "NULLABLE" if s.get("nullable") else "REQUIRED"}
        for s in selected_features
    ]
    return {"fields": fields}


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_pipeline(pipeline: beam.Pipeline, args: argparse.Namespace, contract: dict, domain_cfg: dict) -> None:
    parsed = (
        pipeline
        | "LerPubSub" >> ReadFromPubSub(subscription=args.input_subscription, with_attributes=True)
        | "Validar" >> beam.ParDo(ParseEvent(contract, **domain_cfg)).with_outputs(DEAD_LETTER, main="validos")
    )
    _ = parsed.validos | "GravarBigQuery" >> WriteToBigQuery(
        table=args.output_table,
        schema=bigquery_schema(contract, domain_cfg["event_fields"], domain_cfg["feature_names"]),
        # a tabela e criada antes pelo SQL versionado (particionada e clusterizada)
        create_disposition=BigQueryDisposition.CREATE_NEVER,
        write_disposition=BigQueryDisposition.WRITE_APPEND,
        # streaming inserts aceitam DATETIME/TIMESTAMP como texto ISO e gravam em segundos
        method=WriteToBigQuery.Method.STREAMING_INSERTS,
        insert_retry_strategy=RetryStrategy.RETRY_ON_TRANSIENT_ERROR,
    )
    _ = parsed[DEAD_LETTER] | "PublicarDeadLetter" >> WriteToPubSub(topic=args.dead_letter_topic)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_subscription", required=True)
    parser.add_argument("--output_table", required=True, help="PROJETO:DATASET.TABELA")
    parser.add_argument("--dead_letter_topic", required=True)
    parser.add_argument("--contract", default=str(CONTRACT_PATH), help="caminho de schemas/features.json")
    parser.add_argument("--domain", choices=sorted(DOMAINS), default="voo", help="tipo de evento: voo ou metar")
    args, beam_args = parser.parse_known_args(argv)

    options = PipelineOptions(beam_args)
    options.view_as(StandardOptions).streaming = True
    options.view_as(SetupOptions).save_main_session = False
    contract = load_contract(Path(args.contract))
    domain_cfg = dict(DOMAINS[args.domain])
    if args.domain == "metar":
        domain_cfg["feature_names"] = metar_feature_names(contract)
    with beam.Pipeline(options=options) as pipeline:
        build_pipeline(pipeline, args, contract, domain_cfg)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    main()
