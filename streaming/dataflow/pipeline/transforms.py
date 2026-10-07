"""Transformacoes puras do pipeline: parse e validacao de um evento de voo.

Ficam separadas do pipeline para serem testadas sem Beam e sem GCP. A regra de
validacao vem de schemas/features.json, a mesma fonte da API.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any

# chaves e metadados do evento que nao sao features
EVENT_FIELDS = {
    "event_id": "STRING",
    "event_ts": "TIMESTAMP",
    "nr_voo": "STRING",
    "dt_partida_prevista": "DATETIME",
    "dt_partida_prevista_original": "DATETIME",
    "simulation_run_id": "STRING",
}
REQUIRED_EVENT_FIELDS = ("event_id", "event_ts")


class InvalidEvent(ValueError):
    """Evento que nao respeita o contrato; vai para o dead-letter."""


def _check_feature(spec: dict[str, Any], value: Any) -> Any:
    name = spec["name"]
    if spec["type"] == "STRING":
        if not isinstance(value, str):
            raise InvalidEvent(f"{name} deve ser texto")
        if "enum" in spec and value not in spec["enum"]:
            raise InvalidEvent(f"{name}={value!r} fora do dominio")
        if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
            raise InvalidEvent(f"{name}={value!r} fora do padrao")
        return value
    if spec["type"] == "INT64":
        # bool e subclasse de int em Python; nao e numero valido aqui
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidEvent(f"{name} deve ser inteiro")
        if "minimum" in spec and value < spec["minimum"]:
            raise InvalidEvent(f"{name}={value} abaixo do minimo")
        if "maximum" in spec and value > spec["maximum"]:
            raise InvalidEvent(f"{name}={value} acima do maximo")
        return value
    raise InvalidEvent(f"tipo nao suportado: {spec['type']}")


def _parse_timestamp(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise InvalidEvent(f"{name} deve ser timestamp ISO 8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidEvent(f"{name}={value!r} nao e ISO 8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _parse_datetime(name: str, value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidEvent(f"{name} deve ser DATETIME ISO 8601")
    try:
        # DATETIME do BigQuery nao tem fuso: descarta o offset se vier
        return datetime.fromisoformat(value).replace(tzinfo=None).isoformat()
    except ValueError as exc:
        raise InvalidEvent(f"{name}={value!r} nao e DATETIME ISO 8601") from exc


def parse_event(
    payload: bytes,
    contract: dict[str, Any],
    publish_ts: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Converte a mensagem do Pub/Sub numa linha de tb_anac_stream_eventos.

    Levanta InvalidEvent se o evento violar o contrato. Campos fora do contrato
    e das chaves conhecidas sao recusados: e assim que um campo pos-partida
    (ex.: ds_situacao_partida) nunca chega a tabela.
    """
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidEvent(f"mensagem nao e JSON UTF-8: {exc}") from exc
    if not isinstance(data, dict):
        raise InvalidEvent("mensagem deve ser um objeto JSON")

    features = {spec["name"]: spec for spec in contract["features"]}
    unknown = set(data) - set(features) - set(EVENT_FIELDS)
    if unknown:
        raise InvalidEvent(f"campos fora do contrato: {sorted(unknown)}")
    for name in REQUIRED_EVENT_FIELDS:
        if not data.get(name):
            raise InvalidEvent(f"{name} obrigatorio")
    missing = [name for name in features if name not in data]
    if missing:
        raise InvalidEvent(f"features faltando: {missing}")

    row: dict[str, Any] = {name: _check_feature(spec, data[name]) for name, spec in features.items()}
    if not isinstance(data["event_id"], str):
        raise InvalidEvent("event_id deve ser texto")
    row["event_id"] = data["event_id"]
    row["event_ts"] = _parse_timestamp("event_ts", data["event_ts"])
    row["nr_voo"] = data.get("nr_voo")
    row["simulation_run_id"] = data.get("simulation_run_id")
    row["dt_partida_prevista"] = _parse_datetime("dt_partida_prevista", data.get("dt_partida_prevista"))
    row["dt_partida_prevista_original"] = _parse_datetime(
        "dt_partida_prevista_original", data.get("dt_partida_prevista_original")
    )
    row["publish_ts"] = publish_ts.astimezone(timezone.utc).isoformat() if publish_ts else None
    row["ingest_ts"] = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return row


def dead_letter_record(payload: bytes, error: str, now: datetime | None = None) -> bytes:
    """Mensagem para o dead-letter topic: o payload original mais o motivo."""
    return json.dumps(
        {
            "error": error,
            "failed_at": (now or datetime.now(timezone.utc)).isoformat(),
            "payload": payload.decode("utf-8", errors="replace"),
        },
        ensure_ascii=False,
    ).encode("utf-8")
