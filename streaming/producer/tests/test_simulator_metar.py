from datetime import date, datetime, timezone

from simulator_metar import build_query, load_contract, load_feature_names, observation_offset, to_event

CONTRACT = load_contract()
FEATURES = load_feature_names()
ROW = {
    "sg_icao": "SBGO",
    "dt_observacao_utc": datetime(2024, 12, 20, 13, 0),
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


def test_query_enumera_colunas_e_nao_usa_select_estrela():
    sql = build_query("proj", CONTRACT)
    assert "SELECT *" not in sql.upper()
    for name in FEATURES:
        assert name in sql
    assert "@data_observacao" in sql and "@limite" in sql


def test_query_filtra_so_valor_preenchido_fora_do_contrato():
    sql = build_query("proj", CONTRACT)
    # nullable: o filtro aceita ausencia, so recusa valor preenchido invalido
    assert "nr_umidade_relativa_pct IS NULL OR nr_umidade_relativa_pct >= 0" in sql
    assert "nr_umidade_relativa_pct IS NULL OR nr_umidade_relativa_pct <= 100" in sql
    assert "ds_cobertura_nuvens_1 IS NULL OR ds_cobertura_nuvens_1 IN ('SKC'," in sql


def test_offset_leva_o_dia_historico_para_hoje():
    offset = observation_offset(date(2024, 12, 20), date(2026, 10, 23))
    assert (datetime(2024, 12, 20, 13, 0) + offset) == datetime(2026, 10, 23, 13, 0)


def test_evento_tem_features_do_historico_e_horario_deslocado():
    now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
    offset = observation_offset(date(2024, 12, 20), now.date())
    event = to_event(ROW, FEATURES, offset, "sim-metar-1", now)
    assert event["dt_observacao_utc"] == "2026-10-23T13:00:00"
    assert event["dt_observacao_original"] == "2024-12-20T13:00:00"
    assert event["clima_temperatura_c"] == 24.5
    assert event["clima_rajada_vento_kmh"] is None
    assert event["sg_icao"] == "SBGO"
    assert set(FEATURES) <= set(event)
    assert event["simulation_run_id"] == "sim-metar-1"


def test_event_id_e_unico_por_evento():
    now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
    ids = {
        to_event(ROW, FEATURES, observation_offset(date(2024, 12, 20), now.date()), "r", now)["event_id"]
        for _ in range(50)
    }
    assert len(ids) == 50


def test_evento_do_simulador_passa_na_validacao_do_pipeline():
    # simulador e pipeline compartilham o contrato: o que um publica o outro aceita
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dataflow"))
    from pipeline.run import load_contract as load_contract_pipeline
    from pipeline.transforms import METAR_EVENT_FIELDS, METAR_REQUIRED_EVENT_FIELDS, metar_feature_names, parse_event

    now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
    event = to_event(ROW, FEATURES, observation_offset(date(2024, 12, 20), now.date()), "sim-metar-1", now)
    contract = load_contract_pipeline()
    row = parse_event(
        json.dumps(event).encode(),
        contract,
        now=now,
        event_fields=METAR_EVENT_FIELDS,
        required_event_fields=METAR_REQUIRED_EVENT_FIELDS,
        feature_names=metar_feature_names(contract),
    )
    assert row["clima_cobertura_nuvens"] == "SCT"
