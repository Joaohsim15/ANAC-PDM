"""Transformacoes puras do pipeline: parse e validacao de um evento de METAR.

Ficam separadas do pipeline para serem testadas sem Beam e sem GCP. A regra de
validacao vem de schemas/features.json, a mesma fonte da API: o evento leva as
features de clima do contrato (as nullable, clima_*) mais os metadados da
observacao em METAR_EVENT_FIELDS. Quem publica e
streaming/producer/simulator_metar.py.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any

# chaves e metadados do evento de METAR que nao sao features do contrato. As
# features sao o recorte nullable do contrato (clima_*), ver metar_feature_names
METAR_EVENT_FIELDS = {
    "event_id": "STRING",
    "event_ts": "TIMESTAMP",
    "sg_icao": "STRING",
    "dt_observacao_utc": "DATETIME",
    "dt_observacao_original": "DATETIME",
    "simulation_run_id": "STRING",
}
METAR_REQUIRED_EVENT_FIELDS = ("event_id", "event_ts", "sg_icao")


def metar_feature_names(contract: dict[str, Any]) -> set[str]:
    """As features de METAR sao exatamente as nullable do contrato (clima_*).

    Mesmo recorte usado por streaming/producer/simulator_metar.py.
    """
    return {spec["name"] for spec in contract["features"] if spec.get("nullable")}


class InvalidEvent(ValueError):
    """Evento que nao respeita o contrato; vai para o dead-letter."""


def _check_feature(spec: dict[str, Any], value: Any) -> Any:
    name = spec["name"]
    # nullable: feature pode faltar (ex.: clima sem estacao meteorologica
    # proxima — ver schemas/features.json)
    if value is None:
        if spec.get("nullable", False):
            return None
        raise InvalidEvent(f"{name} e obrigatorio (nao nulo)")
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
    if spec["type"] == "FLOAT64":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidEvent(f"{name} deve ser numero")
        value = float(value)
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
    event_fields: dict[str, str] = METAR_EVENT_FIELDS,
    required_event_fields: tuple[str, ...] = METAR_REQUIRED_EVENT_FIELDS,
    feature_names: set[str] | None = None,
) -> dict[str, Any]:
    """Converte a mensagem do Pub/Sub numa linha da tabela de streaming.

    Levanta InvalidEvent se o evento violar o contrato. Campos fora do
    contrato e das chaves conhecidas sao recusados: e assim que um campo
    pos-partida (ex.: ds_situacao_partida) nunca chega a tabela.

    `feature_names` restringe a validacao a esse subconjunto do contrato; por
    padrao usa metar_feature_names(contract), as features de clima.
    """
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidEvent(f"mensagem nao e JSON UTF-8: {exc}") from exc
    if not isinstance(data, dict):
        raise InvalidEvent("mensagem deve ser um objeto JSON")

    if feature_names is None:
        feature_names = metar_feature_names(contract)
    features = {spec["name"]: spec for spec in contract["features"] if spec["name"] in feature_names}
    unknown = set(data) - set(features) - set(event_fields)
    if unknown:
        raise InvalidEvent(f"campos fora do contrato: {sorted(unknown)}")
    for name in required_event_fields:
        if not data.get(name):
            raise InvalidEvent(f"{name} obrigatorio")
    # feature nullable pode vir ausente da mensagem (equivalente a null);
    # as demais tem que estar presentes
    missing = [name for name in features if name not in data and not features[name].get("nullable", False)]
    if missing:
        raise InvalidEvent(f"features faltando: {missing}")

    row: dict[str, Any] = {
        name: _check_feature(spec, data.get(name)) for name, spec in features.items()
    }
    if not isinstance(data["event_id"], str):
        raise InvalidEvent("event_id deve ser texto")
    row["event_id"] = data["event_id"]
    row["event_ts"] = _parse_timestamp("event_ts", data["event_ts"])
    # demais metadados do evento: genericos por tipo declarado em event_fields
    # (event_id/event_ts ja tratados acima, com parsing proprio)
    for name, bq_type in event_fields.items():
        if name in ("event_id", "event_ts"):
            continue
        if bq_type == "DATETIME":
            row[name] = _parse_datetime(name, data.get(name))
        else:
            row[name] = data.get(name)
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
