"""Explicabilidade por predicao individual, via ML.EXPLAIN_PREDICT.

Diferente do /predict (que serve via Vertex, rapido, no caminho critico da
demo), isto roda a explicacao direto no BigQuery: ENABLE_GLOBAL_EXPLAIN no
CREATE MODEL (sql/ml/model_m1_boosted_tree.sql) so da a importancia GERAL das
features — foi o que usei para investigar por que o clima nao ajudou o AUC
(ver docs/PRD.md P-09/revisao 1.4). ML.EXPLAIN_PREDICT e a contribuicao de
cada feature PARA ESSA PREVISAO especifica. Mais lento que o /predict (e uma
query de BigQuery, nao uma chamada a um endpoint ja carregado) — por isso e
um endpoint separado (/explain), nao uma opcao do /predict.
"""

from typing import Any, Protocol


class ExplainError(RuntimeError):
    """Falha ao obter ou interpretar a explicacao do BigQuery."""


class Explanation:
    __slots__ = ("prob_atraso", "valor_base", "atribuicoes")

    def __init__(self, prob_atraso: float, valor_base: float, atribuicoes: list[dict[str, Any]]) -> None:
        self.prob_atraso = prob_atraso
        self.valor_base = valor_base
        self.atribuicoes = atribuicoes


class Explainer(Protocol):
    model_name: str

    def explain(self, instance: dict[str, Any], top_k: int = 5) -> Explanation: ...


def extract_positive_probability(predicted_label: str, probability: float) -> float:
    """ML.EXPLAIN_PREDICT devolve a probabilidade da classe PREVISTA, nao
    necessariamente de atrasou=1 — inverte quando a classe prevista foi 0,
    para manter o mesmo significado de prob_atraso que o /predict devolve.
    """
    if predicted_label == "1":
        return probability
    if predicted_label == "0":
        return 1.0 - probability
    raise ExplainError(f"rotulo previsto inesperado: {predicted_label!r}")


class BigQueryExplainer:
    def __init__(self, project: str, dataset: str, model: str, feature_types: dict[str, str]) -> None:
        # importacao tardia: os testes usam um explainer falso e nao precisam do SDK
        from google.cloud import bigquery

        self._bigquery = bigquery
        self._client = bigquery.Client(project=project)
        self._model_fqn = f"`{project}.{dataset}.{model}`"
        self._feature_types = feature_types
        self.model_name = f"bigquery:{model}"

    def explain(self, instance: dict[str, Any], top_k: int = 5) -> Explanation:
        bigquery = self._bigquery
        colunas = []
        params = []
        for nome, valor in instance.items():
            tipo = self._feature_types[nome]  # tipo vem do contrato, nao do valor (None nao diz o tipo)
            colunas.append(f"@{nome} AS {nome}")
            params.append(bigquery.ScalarQueryParameter(nome, tipo, valor))
        # ML.EXPLAIN_PREDICT exige literal constante em STRUCT(...) — nao
        # aceita parametro de query aqui. top_k vem do nosso proprio codigo
        # (nunca do payload do usuario), inteiro validado, seguro de interpolar.
        top_k_literal = int(top_k)
        query = f"""
SELECT predicted_atrasou, probability, baseline_prediction_value, top_feature_attributions
FROM ML.EXPLAIN_PREDICT(
  MODEL {self._model_fqn},
  (SELECT {", ".join(colunas)}),
  STRUCT({top_k_literal} AS top_k_features)
)
"""
        try:
            job = self._client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params))
            rows = list(job.result())
        except Exception as exc:  # erros do SDK/BigQuery viram 502 na API
            raise ExplainError(f"falha ao consultar ML.EXPLAIN_PREDICT: {exc}") from exc
        if len(rows) != 1:
            raise ExplainError(f"esperava 1 linha de explicacao, recebeu {len(rows)}")
        row = rows[0]
        prob_atraso = extract_positive_probability(str(row["predicted_atrasou"]), float(row["probability"]))
        atribuicoes = sorted(
            (
                {"feature": a["feature"], "atribuicao": round(float(a["attribution"]), 6)}
                for a in row["top_feature_attributions"]
            ),
            key=lambda a: abs(a["atribuicao"]),
            reverse=True,
        )
        return Explanation(
            prob_atraso=prob_atraso,
            valor_base=round(float(row["baseline_prediction_value"]), 6),
            atribuicoes=atribuicoes,
        )
