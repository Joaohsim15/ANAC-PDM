"""API de predicao de atraso de partida (Cloud Run).

GET  /health  -> disponibilidade, sem chamar o Vertex
POST /predict -> probabilidade de atraso (> 15 min) para um voo
POST /explain -> idem, mais a contribuicao de cada feature para ESSA previsao
                 (ML.EXPLAIN_PREDICT, via BigQuery — mais lento, endpoint
                 separado do caminho critico medido em /predict)
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from typing import Annotated

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .contract import CONTRACT, FlightFeatures
from .explainer import BigQueryExplainer, ExplainError, Explainer
from .predictor import PredictionError, Predictor, VertexPredictor, load_training_means
from .prediction_log import BigQueryPredictionLogger, PredictionLogger

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("anac-api")

FEATURE_TYPES: dict[str, str] = {spec["name"]: spec["type"] for spec in CONTRACT["features"]}

# exemplos prontos na pagina /docs, para testar a API pelo navegador sem montar
# o JSON a mao: voo GLO Goiania -> Guarulhos, sexta, 18 h
_VOO_EXEMPLO = {
    "sg_empresa_icao": "GLO", "sg_icao_origem": "SBGO", "sg_icao_destino": "SBGR",
    "cd_tipo_linha": "N", "sg_equipamento_icao": "B738", "dia_semana": "6", "mes": "12",
    "nr_assentos_ofertados": 186, "hora_partida_prevista": 18, "duracao_prevista_min": 75,
}
EXEMPLOS = {
    "com_trovoada": {
        "summary": "Com METAR: trovoada (TS) na origem",
        "value": {
            **_VOO_EXEMPLO,
            "clima_temperatura_c": 27.0, "clima_umidade_relativa_pct": 74.0,
            "clima_velocidade_vento_kmh": 14.8, "clima_rajada_vento_kmh": None,
            "clima_visibilidade_m": 9999.0, "clima_pressao_hpa": 1012.0,
            "clima_cobertura_nuvens": "SCT", "clima_altura_nuvens_m": 900.0,
            "clima_fenomenos": "TS",
        },
    },
    "sem_estacao": {
        "summary": "Sem METAR: aerodromo sem estacao, clima nulo",
        "value": dict(_VOO_EXEMPLO),
    },
    "invalido": {
        "summary": "Invalido: mes com zero a esquerda e campo pos-partida (422)",
        "value": {**_VOO_EXEMPLO, "mes": "012", "ds_situacao_partida": "Atraso 30-60"},
    },
}


class PredictionResponse(BaseModel):
    prob_atraso: float = Field(..., ge=0.0, le=1.0, description="P(partida > 15 min apos o previsto)")
    modelo: str
    contrato_versao: int
    latencia_ms: float
    predito_em: datetime


class Atribuicao(BaseModel):
    feature: str
    atribuicao: float


class ExplanationResponse(BaseModel):
    prob_atraso: float = Field(..., ge=0.0, le=1.0)
    valor_base: float = Field(..., description="Probabilidade media do modelo, antes de considerar este voo")
    atribuicoes: list[Atribuicao] = Field(..., description="Contribuicao de cada feature para esta previsao, maior |valor| primeiro")
    modelo: str
    contrato_versao: int
    latencia_ms: float
    predito_em: datetime


def build_predictor() -> Predictor:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.environ.get("VERTEX_REGION", "us-central1")
    endpoint_id = os.environ["VERTEX_ENDPOINT_ID"]
    # lido uma vez por instancia: e metadado do modelo, nao dado de voo
    means = load_training_means(
        project=project,
        dataset=os.environ.get("BQ_DATASET", "tf_anac"),
        model=os.environ.get("BQML_MODEL_ID", "mdl_anac_m1_boosted_tree"),
    )
    return VertexPredictor(project=project, region=region, endpoint_id=endpoint_id, training_means=means)


def build_explainer() -> Explainer:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    dataset = os.environ.get("BQ_DATASET", "tf_anac")
    model = os.environ.get("BQML_MODEL_ID", "mdl_anac_m1_boosted_tree")
    return BigQueryExplainer(project=project, dataset=dataset, model=model, feature_types=FEATURE_TYPES)


def _log_prediction_safely(
    prediction_logger: PredictionLogger,
    features: dict,
    prob_atraso: float,
    modelo: str,
    contrato_versao: int,
    nr_voo: str | None,
    dt_referencia: date | None,
    dt_partida_prevista: datetime | None,
) -> None:
    # roda em BackgroundTask, depois da resposta ja enviada: qualquer
    # implementacao de PredictionLogger que falhe nao pode voltar a afetar o
    # /predict (defesa em profundidade; BigQueryPredictionLogger.log ja se
    # protege por conta propria, isto cobre qualquer outra implementacao)
    try:
        prediction_logger.log(features, prob_atraso, modelo, contrato_versao, nr_voo, dt_referencia, dt_partida_prevista)
    except Exception:
        logger.exception("falha ao gravar log de predicao")


def build_prediction_logger() -> PredictionLogger:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    dataset = os.environ.get("BQ_DATASET", "tf_anac")
    return BigQueryPredictionLogger(project=project, dataset=dataset)


def create_app(
    predictor: Predictor | None = None,
    explainer: Explainer | None = None,
    prediction_logger: PredictionLogger | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # injecao nos testes; em producao os clientes nascem uma vez por instancia
        app.state.predictor = predictor or build_predictor()
        app.state.explainer = explainer or build_explainer()
        app.state.prediction_logger = prediction_logger or build_prediction_logger()
        yield

    app = FastAPI(
        title="ANAC-PDM — predicao de atraso de partida",
        version="2.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/predict", response_model=PredictionResponse)
    def predict(
        features: Annotated[FlightFeatures, Body(openapi_examples=EXEMPLOS)],  # type: ignore[valid-type]
        request: Request,
        background_tasks: BackgroundTasks,
        nr_voo: str | None = None,
        dt_referencia: date | None = None,
        dt_partida_prevista: datetime | None = None,
    ) -> PredictionResponse:
        model: Predictor = request.app.state.predictor
        started = time.perf_counter()
        try:
            prob = model.predict_proba([features.model_dump()])[0]
        except PredictionError as exc:
            logger.error("predicao falhou: %s", exc)
            raise HTTPException(status_code=502, detail="falha ao obter a predicao do modelo") from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("predict prob=%.4f latencia_ms=%.1f", prob, elapsed_ms)
        # gravacao e sempre depois da resposta: uma falha de log nunca atrasa
        # ou derruba a predicao (ver _log_prediction_safely)
        background_tasks.add_task(
            _log_prediction_safely,
            request.app.state.prediction_logger,
            features.model_dump(),
            round(prob, 6),
            model.model_name,
            CONTRACT["version"],
            nr_voo,
            dt_referencia,
            dt_partida_prevista,
        )
        return PredictionResponse(
            prob_atraso=round(prob, 6),
            modelo=model.model_name,
            contrato_versao=CONTRACT["version"],
            latencia_ms=round(elapsed_ms, 1),
            predito_em=datetime.now(timezone.utc),
        )

    @app.post("/explain", response_model=ExplanationResponse)
    def explain(
        features: Annotated[FlightFeatures, Body(openapi_examples=EXEMPLOS)],  # type: ignore[valid-type]
        request: Request,
    ) -> ExplanationResponse:
        model: Explainer = request.app.state.explainer
        started = time.perf_counter()
        try:
            explicacao = model.explain(features.model_dump())
        except ExplainError as exc:
            logger.error("explicacao falhou: %s", exc)
            raise HTTPException(status_code=502, detail="falha ao obter a explicacao do modelo") from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("explain prob=%.4f latencia_ms=%.1f", explicacao.prob_atraso, elapsed_ms)
        return ExplanationResponse(
            prob_atraso=round(explicacao.prob_atraso, 6),
            valor_base=explicacao.valor_base,
            atribuicoes=[Atribuicao(**a) for a in explicacao.atribuicoes],
            modelo=model.model_name,
            contrato_versao=CONTRACT["version"],
            latencia_ms=round(elapsed_ms, 1),
            predito_em=datetime.now(timezone.utc),
        )

    return app

