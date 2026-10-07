"""Pipeline Beam: Pub/Sub -> validacao -> BigQuery, com dead-letter.

Uso (Dataflow):
    python -m pipeline.run \\
        --input_subscription projects/$PROJECT/subscriptions/anac-voos-dataflow \\
        --output_table $PROJECT:tf_anac.tb_anac_stream_eventos \\
        --dead_letter_topic projects/$PROJECT/topics/anac-voos-dlq \\
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

from pipeline.transforms import InvalidEvent, dead_letter_record, parse_event

DEAD_LETTER = "dead_letter"
# lido no lancamento e serializado junto com o DoFn: os workers nao leem arquivo
CONTRACT_PATH = Path(__file__).resolve().parents[3] / "schemas" / "features.json"


class ParseEvent(beam.DoFn):
    """Valida cada mensagem; as invalidas saem pela tag de dead-letter."""

    def __init__(self, contract: dict) -> None:
        self._contract = contract
        self._valid = Metrics.counter("anac", "eventos_validos")
        self._invalid = Metrics.counter("anac", "eventos_dead_letter")

    def process(self, message):
        try:
            row = parse_event(message.data, self._contract, publish_ts=message.publish_time)
        except InvalidEvent as exc:
            self._invalid.inc()
            logging.warning("evento invalido: %s", exc)
            yield beam.pvalue.TaggedOutput(DEAD_LETTER, dead_letter_record(message.data, str(exc)))
            return
        self._valid.inc()
        yield row


def bigquery_schema(contract: dict) -> dict:
    fields = [
        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_ts", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "publish_ts", "type": "TIMESTAMP", "mode": "NULLABLE"},
        {"name": "ingest_ts", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "nr_voo", "type": "STRING", "mode": "NULLABLE"},
        {"name": "dt_partida_prevista", "type": "DATETIME", "mode": "NULLABLE"},
        {"name": "dt_partida_prevista_original", "type": "DATETIME", "mode": "NULLABLE"},
        {"name": "simulation_run_id", "type": "STRING", "mode": "NULLABLE"},
    ]
    fields += [{"name": s["name"], "type": s["type"], "mode": "REQUIRED"} for s in contract["features"]]
    return {"fields": fields}


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_pipeline(pipeline: beam.Pipeline, args: argparse.Namespace, contract: dict) -> None:
    parsed = (
        pipeline
        | "LerPubSub" >> ReadFromPubSub(subscription=args.input_subscription, with_attributes=True)
        | "Validar" >> beam.ParDo(ParseEvent(contract)).with_outputs(DEAD_LETTER, main="validos")
    )
    _ = parsed.validos | "GravarBigQuery" >> WriteToBigQuery(
        table=args.output_table,
        schema=bigquery_schema(contract),
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
    args, beam_args = parser.parse_known_args(argv)

    options = PipelineOptions(beam_args)
    options.view_as(StandardOptions).streaming = True
    options.view_as(SetupOptions).save_main_session = False
    contract = load_contract(Path(args.contract))
    with beam.Pipeline(options=options) as pipeline:
        build_pipeline(pipeline, args, contract)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    main()
