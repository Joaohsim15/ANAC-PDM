import pytest
from fastapi.testclient import TestClient

from app.contract import CONTRACT, FEATURE_NAMES
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


@pytest.fixture
def fake():
    return FakePredictor()


@pytest.fixture
def client(fake):
    with TestClient(create_app(predictor=fake)) as c:
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
    # o modelo recebe exatamente as features do contrato, nada a mais
    assert fake.calls == [[VOO_VALIDO]]


@pytest.mark.parametrize("campo", FEATURE_NAMES)
def test_campo_faltando_retorna_422(client, campo):
    payload = {k: v for k, v in VOO_VALIDO.items() if k != campo}
    assert client.post("/predict", json=payload).status_code == 422


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
    with TestClient(create_app(predictor=FakePredictor(fail=True))) as c:
        resp = c.post("/predict", json=VOO_VALIDO)
    assert resp.status_code == 502


def test_contrato_nao_contem_campo_proibido():
    proibidos = set(CONTRACT["forbidden_inputs"])
    assert proibidos.isdisjoint(FEATURE_NAMES)
    assert len(FEATURE_NAMES) == 10


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
