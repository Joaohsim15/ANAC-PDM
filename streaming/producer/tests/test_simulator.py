from datetime import date, datetime, timezone

from simulator import build_query, departure_offset, load_contract, load_feature_names, to_event

CONTRACT = load_contract()
FEATURES = load_feature_names()
ROW = {
    "nr_voo": "1234",
    "dt_partida_prevista": datetime(2024, 12, 20, 18, 30),
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
    # coluna pos-partida que, por engano, viesse da consulta: nao pode sair no evento
    "atraso_partida_minutos": 42,
}


def test_query_enumera_colunas_e_nao_usa_select_estrela():
    sql = build_query("proj", CONTRACT)
    assert "SELECT *" not in sql.upper()
    for name in FEATURES:
        assert name in sql
    assert "atraso_partida_minutos" not in sql
    assert "@data_referencia" in sql and "@limite" in sql


def test_query_filtra_linhas_que_o_contrato_recusaria():
    sql = build_query("proj", CONTRACT)
    assert "nr_assentos_ofertados >= 0" in sql
    assert "nr_assentos_ofertados <= 1000" in sql
    assert "sg_equipamento_icao IS NOT NULL" in sql
    assert "REGEXP_CONTAINS(cd_tipo_linha, r'^[A-Z]$')" in sql
    assert "mes IN ('1'," in sql


def test_offset_leva_o_dia_historico_para_hoje():
    offset = departure_offset(date(2024, 12, 20), date(2026, 10, 23))
    assert (datetime(2024, 12, 20, 18, 30) + offset) == datetime(2026, 10, 23, 18, 30)


def test_evento_tem_features_do_historico_e_horario_deslocado():
    now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
    offset = departure_offset(date(2024, 12, 20), now.date())
    event = to_event(ROW, FEATURES, offset, "sim-1", now)
    assert event["dt_partida_prevista"] == "2026-10-23T18:30:00"
    assert event["dt_partida_prevista_original"] == "2024-12-20T18:30:00"
    # as features continuam as do voo programado, nao as da data da demo
    assert event["mes"] == "12" and event["dia_semana"] == "6"
    assert "atraso_partida_minutos" not in event
    assert set(FEATURES) <= set(event)
    assert event["simulation_run_id"] == "sim-1"


def test_event_id_e_unico_por_evento():
    now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
    ids = {to_event(ROW, FEATURES, departure_offset(date(2024, 12, 20), now.date()), "r", now)["event_id"] for _ in range(50)}
    assert len(ids) == 50


def test_evento_do_simulador_passa_na_validacao_do_pipeline():
    # simulador e pipeline compartilham o contrato: o que um publica o outro aceita
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dataflow"))
    from pipeline.run import load_contract
    from pipeline.transforms import parse_event

    now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
    event = to_event(ROW, FEATURES, departure_offset(date(2024, 12, 20), now.date()), "sim-1", now)
    row = parse_event(json.dumps(event).encode(), load_contract(), now=now)
    assert row["sg_equipamento_icao"] == "B738"
