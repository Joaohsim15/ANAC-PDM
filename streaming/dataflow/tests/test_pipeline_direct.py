"""Roda o DoFn de validacao no DirectRunner, sem Pub/Sub nem BigQuery."""

import json
from datetime import datetime, timezone

import apache_beam as beam
from apache_beam.io.gcp.pubsub import PubsubMessage
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

from pipeline.run import DEAD_LETTER, ParseEvent, load_contract
from tests.test_transforms import EVENTO

CONTRACT = load_contract()


def test_dofn_separa_validos_e_dead_letter():
    publish = datetime(2026, 10, 23, 14, 0, 3, tzinfo=timezone.utc)
    valido = PubsubMessage(json.dumps(EVENTO).encode(), {}, publish_time=publish)
    invalido = PubsubMessage(json.dumps({**EVENTO, "ds_situacao_partida": "x"}).encode(), {}, publish_time=publish)
    lixo = PubsubMessage(b"nao e json", {}, publish_time=publish)

    with TestPipeline() as p:
        out = (
            p
            | beam.Create([valido, invalido, lixo])
            | beam.ParDo(ParseEvent(CONTRACT)).with_outputs(DEAD_LETTER, main="validos")
        )
        assert_that(out.validos | "ids" >> beam.Map(lambda r: r["event_id"]), equal_to([EVENTO["event_id"]]), label="validos")
        assert_that(
            out[DEAD_LETTER] | "erros" >> beam.Map(lambda b: json.loads(b)["error"].split(":")[0]),
            equal_to(["campos fora do contrato", "mensagem nao e JSON UTF-8"]),
            label="dead_letter",
        )
