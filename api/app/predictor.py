"""Cliente do endpoint do Vertex AI.

O modelo servido e o M1 registrado direto do BigQuery ML. O container do Vertex
faz o pre-processamento (codificacao das categorias) e devolve, por instancia:
    {"predicted_atrasou": "1", "atrasou_values": ["1", "0"], "atrasou_probs": [p1, p0]}
A probabilidade de atraso e a posicao do rotulo "1" em atrasou_values.

O container nao reproduz um passo do BigQuery ML: no ML.PREDICT, NULL numerico
vira a media daquela feature no treino. No Vertex, null numerico derruba a
chamada (float(None)) e NaN segue o ramo de ausente da arvore, o que da outra
probabilidade. Por isso a API imputa a media do treino antes de chamar o
endpoint, lida de ML.FEATURE_INFO do mesmo modelo. NULL em STRING o container
aceita como o BigQuery ML.
"""

from typing import Any, Protocol

from .contract import CONTRACT

_NUMERIC_FEATURES = {spec["name"] for spec in CONTRACT["features"] if spec["type"] in ("INT64", "FLOAT64")}


class PredictionError(RuntimeError):
    """Falha ao obter ou interpretar a predicao do endpoint."""


class Predictor(Protocol):
    model_name: str

    def predict_proba(self, instances: list[dict[str, Any]]) -> list[float]: ...


def extract_positive_proba(prediction: Any, label: str = "atrasou") -> float:
    """Extrai P(label = 1) de uma predicao do container BQML."""
    if not isinstance(prediction, dict):
        raise PredictionError(f"predicao em formato inesperado: {type(prediction).__name__}")
    values = prediction.get(f"{label}_values")
    probs = prediction.get(f"{label}_probs")
    if not values or not probs or len(values) != len(probs):
        raise PredictionError(f"predicao sem {label}_values/{label}_probs coerentes")
    for value, prob in zip(values, probs):
        if str(value) == "1":
            return float(prob)
    raise PredictionError(f"rotulo '1' ausente em {label}_values={values}")


def impute_numeric_nulls(instance: dict[str, Any], means: dict[str, float]) -> dict[str, Any]:
    """Troca null numerico pela media do treino, como o ML.PREDICT faz."""
    imputed = dict(instance)
    for name, value in instance.items():
        if value is None and name in means:
            imputed[name] = means[name]
        elif value is None and name in _NUMERIC_FEATURES:
            raise PredictionError(f"sem media de treino para imputar {name}")
    return imputed


def load_training_means(project: str, dataset: str, model: str) -> dict[str, float]:
    """Medias das features numericas no treino, de ML.FEATURE_INFO."""
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    rows = client.query(
        f"SELECT input, mean FROM ML.FEATURE_INFO(MODEL `{project}.{dataset}.{model}`) WHERE mean IS NOT NULL"
    ).result()
    means = {row["input"]: float(row["mean"]) for row in rows}
    missing = _NUMERIC_FEATURES - set(means)
    if missing:
        raise RuntimeError(f"ML.FEATURE_INFO sem media para {sorted(missing)}")
    return means


class VertexPredictor:
    def __init__(self, project: str, region: str, endpoint_id: str, training_means: dict[str, float]) -> None:
        # importacao tardia: os testes usam um preditor falso e nao precisam do SDK
        from google.cloud import aiplatform

        aiplatform.init(project=project, location=region)
        self._endpoint = aiplatform.Endpoint(endpoint_id)
        self._training_means = training_means
        self.model_name = f"vertex:{endpoint_id}"

    def predict_proba(self, instances: list[dict[str, Any]]) -> list[float]:
        instances = [impute_numeric_nulls(i, self._training_means) for i in instances]
        try:
            response = self._endpoint.predict(instances=instances)
        except Exception as exc:  # erros do SDK viram 502 na API
            raise PredictionError(f"falha ao chamar o endpoint: {exc}") from exc
        if len(response.predictions) != len(instances):
            raise PredictionError("quantidade de predicoes diferente da de instancias")
        return [extract_positive_proba(p) for p in response.predictions]
