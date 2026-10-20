import pytest
from fastapi.testclient import TestClient

from app.contract import CONTRACT, FEATURE_NAMES
from app.explainer import ExplainError, Explanation
from app.main import create_app
from app.predictor import PredictionError, extract_positive_proba

VOO_VALIDO = {
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


class FakePredictor:
    model_name = "fake"

    def __init__(self, prob: float = 0.61, fail: bool = False) -> None:
        self.prob = prob
        self.fail = fail
        self.calls: list[list[dict]] = []

    def predict_proba(self, instances):
        self.calls.append(instances)
        if self.fail:
            raise PredictionError("endpoint fora do ar")
        return [self.prob for _ in instances]


class FakeExplainer:
    model_name = "fake-explain"

    def __init__(self, prob: float = 0.61, valor_base: float = 0.5, atribuicoes: list[dict] | None = None, fail: bool = False) -> None:
        self.prob = prob
        self.valor_base = valor_base
        self.atribuicoes = atribuicoes if atribuicoes is not None else [{"feature": "mes", "atribuicao": 0.1}]
        self.fail = fail
        self.calls: list[dict] = []

    def explain(self, instance, top_k=5):
        self.calls.append(instance)
        if self.fail:
            raise ExplainError("bigquery fora do ar")
        return Explanation(prob_atraso=self.prob, valor_base=self.valor_base, atribuicoes=self.atribuicoes)


class FakePredictionLogger:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    def log(self, features, prob_atraso, modelo, contrato_versao, nr_voo, dt_referencia, dt_partida_prevista):
        if self.fail:
            raise RuntimeError("bigquery fora do ar")
        self.calls.append(
            {
                "features": features,
                "prob_atraso": prob_atraso,
                "modelo": modelo,
                "contrato_versao": contrato_versao,
                "nr_voo": nr_voo,
                "dt_referencia": dt_referencia,
                "dt_partida_prevista": dt_partida_prevista,
            }
        )


@pytest.fixture
def fake():
    return FakePredictor()


@pytest.fixture
def fake_explainer():
    return FakeExplainer()


@pytest.fixture
def fake_logger():
    return FakePredictionLogger()


@pytest.fixture
def client(fake, fake_explainer, fake_logger):
    with TestClient(create_app(predictor=fake, explainer=fake_explainer, prediction_logger=fake_logger)) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_predict_retorna_probabilidade(client, fake):
    resp = client.post("/predict", json=VOO_VALIDO)
    assert resp.status_code == 200
    body = resp.json()
    assert body["prob_atraso"] == pytest.approx(0.61)
    assert body["modelo"] == "fake"
    assert body["contrato_versao"] == CONTRACT["version"]
    # o modelo recebe exatamente as features do contrato, nada a mais — as
    # nullable ausentes do payload chegam como None, nao ficam de fora
    esperado = {**VOO_VALIDO, **{campo: None for campo in FEATURE_NAMES if campo not in VOO_VALIDO}}
    assert fake.calls == [[esperado]]


CAMPOS_OBRIGATORIOS = [spec["name"] for spec in CONTRACT["features"] if not spec.get("nullable")]
CAMPOS_NULLABLE = [spec["name"] for spec in CONTRACT["features"] if spec.get("nullable")]


@pytest.mark.parametrize("campo", CAMPOS_OBRIGATORIOS)
def test_campo_faltando_retorna_422(client, campo):
    payload = {k: v for k, v in VOO_VALIDO.items() if k != campo}
    assert client.post("/predict", json=payload).status_code == 422


def test_campos_nullable_ausentes_sao_aceitos(client, fake):
    # VOO_VALIDO ja nao inclui as features de clima — precisam ser opcionais
    # (aerodromo sem estacao meteorologica, ver docs/PRD.md P-09)
    assert not set(CAMPOS_NULLABLE) & set(VOO_VALIDO)
    resp = client.post("/predict", json=VOO_VALIDO)
    assert resp.status_code == 200
    assert all(fake.calls[-1][0].get(campo) is None for campo in CAMPOS_NULLABLE)


def test_campos_nullable_explicitos_null_sao_aceitos(client):
    payload = {**VOO_VALIDO, **{campo: None for campo in CAMPOS_NULLABLE}}
    assert client.post("/predict", json=payload).status_code == 200


def test_campo_clima_preenchido_e_aceito(client, fake):
    payload = {
        **VOO_VALIDO,
        "clima_temperatura_c": 22.5,
        "clima_umidade_relativa_pct": 78.0,
        "clima_velocidade_vento_kmh": 11.1,
        "clima_rajada_vento_kmh": None,
        "clima_visibilidade_m": 9999.0,
        "clima_pressao_hpa": 1013.2,
        "clima_cobertura_nuvens": "SCT",
        "clima_altura_nuvens_m": 450.0,
        "clima_fenomenos": "RA",
    }
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 200
    assert fake.calls[-1][0]["clima_temperatura_c"] == 22.5
    assert fake.calls[-1][0]["clima_cobertura_nuvens"] == "SCT"


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("clima_temperatura_c", -50),  # abaixo do minimo
        ("clima_umidade_relativa_pct", 150),  # acima de 100
        ("clima_cobertura_nuvens", "XXX"),  # fora do dominio
        ("clima_temperatura_c", "22.5"),  # numero como texto e recusado
    ],
)
def test_valor_invalido_de_clima_retorna_422(client, campo, valor):
    assert client.post("/predict", json={**VOO_VALIDO, campo: valor}).status_code == 422


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("dia_semana", "8"),  # fora de 1..7
        ("mes", "01"),  # o modelo foi treinado sem zero a esquerda
        ("cd_tipo_linha", "NN"),
        ("cd_tipo_linha", "n"),
        ("sg_equipamento_icao", "B7381"),
        ("sg_icao_origem", "sbgo"),  # ICAO em minusculas nao existe no vocabulario
        ("sg_empresa_icao", "GOL1"),
        ("hora_partida_prevista", 24),
        ("duracao_prevista_min", 5),
        ("nr_assentos_ofertados", -1),
        ("hora_partida_prevista", "18"),  # numero como texto e recusado
    ],
)
def test_valor_invalido_retorna_422(client, campo, valor):
    assert client.post("/predict", json={**VOO_VALIDO, campo: valor}).status_code == 422


@pytest.mark.parametrize(
    "campo_proibido",
    ["ds_situacao_partida", "dt_partida_real", "ds_justificativa", "atraso_partida_minutos"],
)
def test_campos_pos_partida_sao_recusados(client, campo_proibido):
    # vazamento de alvo: informacao posterior a decolagem nunca entra no payload
    resp = client.post("/predict", json={**VOO_VALIDO, campo_proibido: "x"})
    assert resp.status_code == 422


def test_falha_do_modelo_retorna_502():
    app = create_app(predictor=FakePredictor(fail=True), explainer=FakeExplainer(), prediction_logger=FakePredictionLogger())
    with TestClient(app) as c:
        resp = c.post("/predict", json=VOO_VALIDO)
    assert resp.status_code == 502


def test_predict_loga_a_predicao_em_background(client, fake_logger):
    resp = client.post("/predict", json=VOO_VALIDO)
    assert resp.status_code == 200
    assert len(fake_logger.calls) == 1
    chamada = fake_logger.calls[0]
    assert chamada["prob_atraso"] == pytest.approx(0.61)
    assert chamada["modelo"] == "fake"
    assert chamada["contrato_versao"] == CONTRACT["version"]
    assert chamada["features"]["sg_empresa_icao"] == "GLO"
    # sem parametro de reconciliacao na chamada: chave vai nula, nao quebra
    assert chamada["nr_voo"] is None
    assert chamada["dt_referencia"] is None
    assert chamada["dt_partida_prevista"] is None


def test_predict_com_parametros_de_reconciliacao(client, fake_logger):
    resp = client.post(
        "/predict?nr_voo=1234&dt_referencia=2024-12-20&dt_partida_prevista=2024-12-20T18:30:00",
        json=VOO_VALIDO,
    )
    assert resp.status_code == 200
    chamada = fake_logger.calls[0]
    assert chamada["nr_voo"] == "1234"
    assert str(chamada["dt_referencia"]) == "2024-12-20"
    assert str(chamada["dt_partida_prevista"]) == "2024-12-20 18:30:00"


def test_predict_nao_falha_se_o_log_falhar(fake, fake_explainer):
    app = create_app(predictor=fake, explainer=fake_explainer, prediction_logger=FakePredictionLogger(fail=True))
    with TestClient(app) as c:
        resp = c.post("/predict", json=VOO_VALIDO)
    assert resp.status_code == 200
    assert resp.json()["prob_atraso"] == pytest.approx(0.61)


def test_explain_retorna_contribuicoes(client, fake_explainer):
    resp = client.post("/explain", json=VOO_VALIDO)
    assert resp.status_code == 200
    body = resp.json()
    assert body["prob_atraso"] == pytest.approx(0.61)
    assert body["valor_base"] == pytest.approx(0.5)
    assert body["atribuicoes"] == [{"feature": "mes", "atribuicao": 0.1}]
    assert body["modelo"] == "fake-explain"
    assert fake_explainer.calls[0]["sg_empresa_icao"] == "GLO"


def test_explain_valida_payload_como_predict(client):
    payload = {k: v for k, v in VOO_VALIDO.items() if k != "sg_empresa_icao"}
    assert client.post("/explain", json=payload).status_code == 422


def test_explain_falha_retorna_502(fake, fake_logger):
    app = create_app(predictor=fake, explainer=FakeExplainer(fail=True), prediction_logger=fake_logger)
    with TestClient(app) as c:
        resp = c.post("/explain", json=VOO_VALIDO)
    assert resp.status_code == 502


def test_contrato_nao_contem_campo_proibido():
    proibidos = set(CONTRACT["forbidden_inputs"])
    assert proibidos.isdisjoint(FEATURE_NAMES)
    assert len(FEATURE_NAMES) == 19
    assert len(CAMPOS_OBRIGATORIOS) == 10
    assert len(CAMPOS_NULLABLE) == 9


def test_extract_positive_proba_pega_o_rotulo_1():
    # formato real do container BQML: a ordem dos rotulos nao e garantida
    pred = {"predicted_atrasou": "1", "atrasou_values": ["1", "0"], "atrasou_probs": [0.63, 0.37]}
    assert extract_positive_proba(pred) == pytest.approx(0.63)
    pred_invertida = {"atrasou_values": ["0", "1"], "atrasou_probs": [0.8, 0.2]}
    assert extract_positive_proba(pred_invertida) == pytest.approx(0.2)


@pytest.mark.parametrize(
    "pred",
    [None, {}, {"atrasou_values": ["0"], "atrasou_probs": [0.1, 0.9]}, {"atrasou_values": ["0", "2"], "atrasou_probs": [0.5, 0.5]}],
)
def test_extract_positive_proba_recusa_formato_inesperado(pred):
    with pytest.raises(PredictionError):
        extract_positive_proba(pred)
