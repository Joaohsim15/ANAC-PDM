import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline.run import bigquery_schema, load_contract
from pipeline.transforms import InvalidEvent, dead_letter_record, metar_feature_names, parse_event

CONTRACT = load_contract()
NOW = datetime(2026, 10, 23, 14, 0, 5, tzinfo=timezone.utc)
PUBLISH = datetime(2026, 10, 23, 14, 0, 3, tzinfo=timezone.utc)
METAR_FEATURES = metar_feature_names(CONTRACT)

EVENTO = {
    "event_id": "6f1c3a0e-0000-4000-8000-000000000002",
    "event_ts": "2026-10-23T14:00:00Z",
    "sg_icao": "SBGO",
    "dt_observacao_utc": "2026-10-23T13:00:00",
    "dt_observacao_original": "2024-12-20T13:00:00",
    "simulation_run_id": "demo-metar-1",
    "clima_temperatura_c": 24.5,
    "clima_umidade_relativa_pct": 70.0,
    "clima_velocidade_vento_kmh": 12.0,
    "clima_rajada_vento_kmh": None,
    "clima_visibilidade_m": 9999.0,
    "clima_pressao_hpa": 1013.0,
    "clima_cobertura_nuvens": "SCT",
    "clima_altura_nuvens_m": 600.0,
    "clima_fenomenos": "",
}


def _msg(evento: dict) -> bytes:
    return json.dumps(evento).encode("utf-8")


def test_features_do_evento_sao_as_de_clima_do_contrato():
    assert METAR_FEATURES == {s["name"] for s in CONTRACT["features"] if s["name"].startswith("clima_")}


def test_evento_valido_vira_linha_da_tabela():
    row = parse_event(_msg(EVENTO), CONTRACT, publish_ts=PUBLISH, now=NOW)
    assert row["sg_icao"] == "SBGO"
    assert row["event_ts"] == "2026-10-23T14:00:00+00:00"
    assert row["publish_ts"] == "2026-10-23T14:00:03+00:00"
    assert row["ingest_ts"] == "2026-10-23T14:00:05+00:00"
    assert row["dt_observacao_utc"] == "2026-10-23T13:00:00"
    assert row["clima_temperatura_c"] == 24.5
    assert row["clima_rajada_vento_kmh"] is None
    # toda coluna da linha existe no schema do BigQuery, e vice-versa
    schema_cols = {f["name"] for f in bigquery_schema(CONTRACT)["fields"]}
    assert set(row) == schema_cols


def test_feature_de_clima_ausente_e_aceita():
    # estacao sem aquele sensor naquela observacao: ausencia vale como null
    evento = {k: v for k, v in EVENTO.items() if k != "clima_temperatura_c"}
    row = parse_event(_msg(evento), CONTRACT, now=NOW)
    assert row["clima_temperatura_c"] is None


@pytest.mark.parametrize(
    "mutacao",
    [
        {"clima_temperatura_c": -50},  # abaixo do minimo
        {"clima_umidade_relativa_pct": "70"},  # texto em campo numerico
        {"clima_visibilidade_m": True},
        {"clima_cobertura_nuvens": "XXX"},  # fora do dominio
        {"clima_fenomenos": "ra"},  # minusculo, fora do padrao
        {"event_ts": "ontem"},
        {"event_id": ""},
        {"dt_observacao_utc": "13h"},
    ],
)
def test_evento_invalido_levanta(mutacao):
    with pytest.raises(InvalidEvent):
        parse_event(_msg({**EVENTO, **mutacao}), CONTRACT, now=NOW)


def test_evento_sem_sg_icao_levanta():
    evento = {k: v for k, v in EVENTO.items() if k != "sg_icao"}
    with pytest.raises(InvalidEvent):
        parse_event(_msg(evento), CONTRACT, now=NOW)


@pytest.mark.parametrize("campo", ["sg_empresa_icao", "ds_situacao_partida", "dt_partida_real"])
def test_campo_fora_do_evento_de_metar_e_recusado(campo):
    # campos de voo e pos-partida nunca chegam a tabela de METAR
    with pytest.raises(InvalidEvent, match="campos fora do contrato"):
        parse_event(_msg({**EVENTO, campo: "x"}), CONTRACT, now=NOW)


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
    ddl = (Path(__file__).resolve().parents[3] / "sql/streaming/create_table_stream_metar.sql").read_text()
    for field in bigquery_schema(CONTRACT)["fields"]:
        assert f"\n  {field['name']} " in ddl, f"coluna {field['name']} ausente no DDL"
