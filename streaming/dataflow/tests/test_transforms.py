import json
from datetime import datetime, timezone

import pytest

from pipeline.run import bigquery_schema, load_contract
from pipeline.transforms import InvalidEvent, dead_letter_record, parse_event

CONTRACT = load_contract()
NOW = datetime(2026, 10, 23, 14, 0, 5, tzinfo=timezone.utc)
PUBLISH = datetime(2026, 10, 23, 14, 0, 3, tzinfo=timezone.utc)

EVENTO = {
    "event_id": "6f1c3a0e-0000-4000-8000-000000000001",
    "event_ts": "2026-10-23T14:00:00Z",
    "nr_voo": "1234",
    "dt_partida_prevista": "2026-10-23T18:30:00",
    "dt_partida_prevista_original": "2024-12-20T18:30:00",
    "simulation_run_id": "demo-1",
    "sg_empresa_icao": "GLO",
    "sg_icao_origem": "SBGO",
    "sg_icao_destino": "SBGR",
    "cd_tipo_linha": "N",
    "sg_equipamento_icao": "B738",
    "dia_semana": "6",
    "mes": "12",
    "nr_assentos_ofertados": 186,
    "hora_partida_prevista": 18,
    "duracao_prevista_min": 75,
}


def _msg(evento: dict) -> bytes:
    return json.dumps(evento).encode("utf-8")


def test_evento_valido_vira_linha_da_tabela():
    row = parse_event(_msg(EVENTO), CONTRACT, publish_ts=PUBLISH, now=NOW)
    assert row["event_ts"] == "2026-10-23T14:00:00+00:00"
    assert row["publish_ts"] == "2026-10-23T14:00:03+00:00"
    assert row["ingest_ts"] == "2026-10-23T14:00:05+00:00"
    assert row["dt_partida_prevista"] == "2026-10-23T18:30:00"
    assert row["nr_assentos_ofertados"] == 186
    # toda coluna da linha existe no schema do BigQuery, e vice-versa
    schema_cols = {f["name"] for f in bigquery_schema(CONTRACT)["fields"]}
    assert set(row) == schema_cols


@pytest.mark.parametrize(
    "mutacao",
    [
        {"ds_situacao_partida": "Atraso 30-60"},  # pos-partida: vazamento de alvo
        {"dt_partida_real": "2026-10-23T19:10:00"},
        {"mes": "01"},
        {"dia_semana": 7.0},
        {"nr_assentos_ofertados": "186"},
        {"nr_assentos_ofertados": True},
        {"hora_partida_prevista": 24},
        {"sg_icao_origem": "SB"},
        {"event_ts": "ontem"},
        {"event_id": ""},
    ],
)
def test_evento_invalido_levanta(mutacao):
    with pytest.raises(InvalidEvent):
        parse_event(_msg({**EVENTO, **mutacao}), CONTRACT, now=NOW)


@pytest.mark.parametrize("feature", [s["name"] for s in CONTRACT["features"]])
def test_feature_faltando_levanta(feature):
    evento = {k: v for k, v in EVENTO.items() if k != feature}
    with pytest.raises(InvalidEvent):
        parse_event(_msg(evento), CONTRACT, now=NOW)


@pytest.mark.parametrize("payload", [b"nao e json", b"[1, 2]", b"\xff\xfe"])
def test_payload_malformado_levanta(payload):
    with pytest.raises(InvalidEvent):
        parse_event(payload, CONTRACT, now=NOW)


def test_dead_letter_preserva_payload_e_motivo():
    record = json.loads(dead_letter_record(b'{"x": 1}', "campos fora do contrato", now=NOW))
    assert record == {
        "error": "campos fora do contrato",
        "failed_at": "2026-10-23T14:00:05+00:00",
        "payload": '{"x": 1}',
    }


def test_schema_bate_com_o_ddl_versionado():
    from pathlib import Path

    ddl = (Path(__file__).resolve().parents[3] / "sql/streaming/create_table_stream_eventos.sql").read_text()
    for field in bigquery_schema(CONTRACT)["fields"]:
        assert f"\n  {field['name']} " in ddl, f"coluna {field['name']} ausente no DDL"
