"""API de predicao de atraso de partida (Cloud Run).

GET  /health  -> disponibilidade, sem chamar o Vertex
POST /predict -> probabilidade de atraso (> 15 min) para um voo
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .contract import CONTRACT, FlightFeatures
from .predictor import PredictionError, Predictor, VertexPredictor

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("anac-api")


class PredictionResponse(BaseModel):
    prob_atraso: float = Field(..., ge=0.0, le=1.0, description="P(partida > 15 min apos o previsto)")
    modelo: str
    contrato_versao: int
    latencia_ms: float
    predito_em: datetime


def build_predictor() -> Predictor:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.environ.get("VERTEX_REGION", "us-central1")
    endpoint_id = os.environ["VERTEX_ENDPOINT_ID"]
    return VertexPredictor(project=project, region=region, endpoint_id=endpoint_id)


def create_app(predictor: Predictor | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # injecao nos testes; em producao o cliente nasce uma vez por instancia
        app.state.predictor = predictor or build_predictor()
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
    def predict(features: FlightFeatures, request: Request) -> PredictionResponse:  # type: ignore[valid-type]
        model: Predictor = request.app.state.predictor
        started = time.perf_counter()
        try:
            prob = model.predict_proba([features.model_dump()])[0]
        except PredictionError as exc:
            logger.error("predicao falhou: %s", exc)
            raise HTTPException(status_code=502, detail="falha ao obter a predicao do modelo") from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("predict prob=%.4f latencia_ms=%.1f", prob, elapsed_ms)
        return PredictionResponse(
            prob_atraso=round(prob, 6),
            modelo=model.model_name,
            contrato_versao=CONTRACT["version"],
            latencia_ms=round(elapsed_ms, 1),
            predito_em=datetime.now(timezone.utc),
        )

    return app

