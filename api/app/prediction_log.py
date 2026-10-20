"""Log de cada predicao feita pela API, para medir acuracia em producao.

Grava de forma assincrona (nao bloqueia a resposta do /predict, roda depois
dela como BackgroundTask) numa tabela separada,
sql/ml/create_table_predicoes_log.sql. O contrato de features
(schemas/features.json) continua intocado: nr_voo/dt_referencia/
dt_partida_prevista NAO sao features do modelo, so chaves OPCIONAIS para
reconciliar depois com o resultado real na Gold (sql/ml/reconciliar_predicoes.sql)
— payload autocontido do /predict nao muda.
"""

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Protocol

logger = logging.getLogger("anac-api.prediction_log")


class PredictionLogger(Protocol):
    def log(
        self,
        features: dict[str, Any],
        prob_atraso: float,
        modelo: str,
        contrato_versao: int,
        nr_voo: str | None,
        dt_referencia: date | None,
        dt_partida_prevista: datetime | None,
    ) -> None: ...


class BigQueryPredictionLogger:
    def __init__(self, project: str, dataset: str, table: str = "tb_anac_predicoes_log") -> None:
        # importacao tardia: os testes usam um logger falso e nao precisam do SDK
        from google.cloud import bigquery

        self._client = bigquery.Client(project=project)
        self._table_id = f"{project}.{dataset}.{table}"

    def log(
        self,
        features: dict[str, Any],
        prob_atraso: float,
        modelo: str,
        contrato_versao: int,
        nr_voo: str | None,
        dt_referencia: date | None,
        dt_partida_prevista: datetime | None,
    ) -> None:
        row = {
            "prediction_id": str(uuid.uuid4()),
            "predicted_em": datetime.now(timezone.utc).isoformat(),
            "modelo": modelo,
            "contrato_versao": contrato_versao,
            "prob_atraso": prob_atraso,
            "nr_voo": nr_voo,
            "dt_referencia": dt_referencia.isoformat() if dt_referencia else None,
            "dt_partida_prevista": dt_partida_prevista.isoformat() if dt_partida_prevista else None,
            **features,
        }
        try:
            errors = self._client.insert_rows_json(self._table_id, [row])
        except Exception:
            # log e auxiliar: uma falha aqui nunca pode derrubar a predicao
            # (ja respondida ao chamador antes desta tarefa rodar)
            logger.exception("falha ao gravar log de predicao")
            return
        if errors:
            logger.warning("BigQuery recusou o insert do log de predicao: %s", errors)
