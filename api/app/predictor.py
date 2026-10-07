"""Cliente do endpoint do Vertex AI.

O modelo servido e o M1 registrado direto do BigQuery ML. O container do Vertex
faz o pre-processamento (codificacao das categorias) e devolve, por instancia:
    {"predicted_atrasou": "1", "atrasou_values": ["1", "0"], "atrasou_probs": [p1, p0]}
A probabilidade de atraso e a posicao do rotulo "1" em atrasou_values.
"""

from typing import Any, Protocol


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


class VertexPredictor:
    def __init__(self, project: str, region: str, endpoint_id: str) -> None:
        # importacao tardia: os testes usam um preditor falso e nao precisam do SDK
        from google.cloud import aiplatform

        aiplatform.init(project=project, location=region)
        self._endpoint = aiplatform.Endpoint(endpoint_id)
        self.model_name = f"vertex:{endpoint_id}"

    def predict_proba(self, instances: list[dict[str, Any]]) -> list[float]:
        try:
            response = self._endpoint.predict(instances=instances)
        except Exception as exc:  # erros do SDK viram 502 na API
            raise PredictionError(f"falha ao chamar o endpoint: {exc}") from exc
        if len(response.predictions) != len(instances):
            raise PredictionError("quantidade de predicoes diferente da de instancias")
        return [extract_positive_proba(p) for p in response.predictions]
