import json
from datetime import datetime, timezone

import pytest

from pipeline.run import bigquery_schema, load_contract
from pipeline.transforms import (
    METAR_EVENT_FIELDS,
    METAR_REQUIRED_EVENT_FIELDS,
    InvalidEvent,
    dead_letter_record,
    metar_feature_names,
    parse_event,
)

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


CAMPOS_OBRIGATORIOS = [s["name"] for s in CONTRACT["features"] if not s.get("nullable")]
CAMPOS_NULLABLE = [s["name"] for s in CONTRACT["features"] if s.get("nullable")]


@pytest.mark.parametrize("feature", CAMPOS_OBRIGATORIOS)
def test_feature_faltando_levanta(feature):
    evento = {k: v for k, v in EVENTO.items() if k != feature}
    with pytest.raises(InvalidEvent):
        parse_event(_msg(evento), CONTRACT, now=NOW)


def test_feature_nullable_ausente_e_aceita():
    # EVENTO ja nao traz as features de clima — o evento de voo nao carrega
    # meteorologia (isso fica pro stream de METAR); precisam ser aceitas como
    # ausentes aqui tambem
    assert not set(CAMPOS_NULLABLE) & set(EVENTO)
    row = parse_event(_msg(EVENTO), CONTRACT, now=NOW)
    assert all(row[campo] is None for campo in CAMPOS_NULLABLE)


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

    # tb_anac_stream_eventos carrega eventos de VOO, nao de clima — a
    # meteorologia tem seu proprio stream (sql/streaming/create_table_stream_metar.sql,
    # testado em test_schema_metar_bate_com_o_ddl_versionado abaixo) e sua
    # propria tabela. So os campos de voo do contrato precisam estar nesta
    # DDL especifica.
    ddl = (Path(__file__).resolve().parents[3] / "sql/streaming/create_table_stream_eventos.sql").read_text()
    campos_de_voo = {"event_id", "event_ts", "publish_ts", "ingest_ts", "nr_voo",
                      "dt_partida_prevista", "dt_partida_prevista_original", "simulation_run_id"}
    campos_de_voo |= set(CAMPOS_OBRIGATORIOS)
    for field in bigquery_schema(CONTRACT)["fields"]:
        if field["name"] not in campos_de_voo:
            continue
        assert f"\n  {field['name']} " in ddl, f"coluna {field['name']} ausente no DDL"


# ============================================================================
# Dominio METAR: mesma validacao, metadados e recorte de features diferentes
# (sg_icao/dt_observacao_utc no lugar de nr_voo/dt_partida_prevista; so as
# features nullable do contrato, clima_*)
# ============================================================================

METAR_FEATURES = metar_feature_names(CONTRACT)

EVENTO_METAR = {
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


def _parse_metar(evento: dict) -> dict:
    return parse_event(
        _msg(evento),
        CONTRACT,
        now=NOW,
        event_fields=METAR_EVENT_FIELDS,
        required_event_fields=METAR_REQUIRED_EVENT_FIELDS,
        feature_names=METAR_FEATURES,
    )


def test_evento_metar_valido_vira_linha_da_tabela():
    row = _parse_metar(EVENTO_METAR)
    assert row["sg_icao"] == "SBGO"
    assert row["dt_observacao_utc"] == "2026-10-23T13:00:00"
    assert row["clima_temperatura_c"] == 24.5
    assert row["clima_rajada_vento_kmh"] is None
    schema_cols = {f["name"] for f in bigquery_schema(CONTRACT, METAR_EVENT_FIELDS, METAR_FEATURES)["fields"]}
    assert set(row) == schema_cols


@pytest.mark.parametrize(
    "mutacao",
    [
        {"clima_temperatura_c": -50},  # abaixo do minimo
        {"clima_cobertura_nuvens": "XXX"},  # fora do dominio
        {"clima_fenomenos": "ra"},  # minusculo, fora do padrao
    ],
)
def test_evento_metar_invalido_levanta(mutacao):
    with pytest.raises(InvalidEvent):
        _parse_metar({**EVENTO_METAR, **mutacao})


def test_evento_metar_sem_sg_icao_levanta():
    evento = {k: v for k, v in EVENTO_METAR.items() if k != "sg_icao"}
    with pytest.raises(InvalidEvent):
        _parse_metar(evento)


def test_evento_metar_recusa_campo_de_voo():
    # sg_empresa_icao e feature de voo, fora do recorte metar_feature_names
    with pytest.raises(InvalidEvent):
        _parse_metar({**EVENTO_METAR, "sg_empresa_icao": "GLO"})


def test_schema_metar_bate_com_o_ddl_versionado():
    from pathlib import Path

    ddl = (Path(__file__).resolve().parents[3] / "sql/streaming/create_table_stream_metar.sql").read_text()
    for field in bigquery_schema(CONTRACT, METAR_EVENT_FIELDS, METAR_FEATURES)["fields"]:
        assert f"\n  {field['name']} " in ddl, f"coluna {field['name']} ausente no DDL de METAR"
