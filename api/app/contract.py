"""Modelo de validacao do payload, gerado a partir de schemas/features.json.

O contrato nao e reescrito a mao aqui: o modelo pydantic e montado em tempo de
importacao lendo o JSON, para que API e contrato nunca divirjam.
"""

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

# Na imagem Docker o contrato e copiado para /app/schemas; no repositorio fica
# dois niveis acima de api/app.
_DEFAULT_PATHS = (
    Path(__file__).resolve().parents[1] / "schemas" / "features.json",
    Path(__file__).resolve().parents[2] / "schemas" / "features.json",
)


def load_contract(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    candidates = [Path(path)] if path else [Path(p) for p in _DEFAULT_PATHS]
    env_path = os.environ.get("FEATURES_CONTRACT_PATH")
    if env_path and not path:
        candidates.insert(0, Path(env_path))
    for candidate in candidates:
        if candidate.is_file():
            with candidate.open(encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(f"schemas/features.json nao encontrado em {candidates}")


def _field_for(spec: dict[str, Any]) -> tuple[Any, Any]:
    description = spec.get("description")
    if spec["type"] == "STRING":
        if "enum" in spec:
            return Literal[tuple(spec["enum"])], Field(..., description=description)
        return str, Field(..., description=description, pattern=spec.get("pattern"))
    if spec["type"] == "INT64":
        # strict: recusa "18" (string) e 18.5 (float) em vez de converter calado
        return int, Field(
            ...,
            description=description,
            ge=spec.get("minimum"),
            le=spec.get("maximum"),
            strict=True,
        )
    raise ValueError(f"Tipo nao suportado no contrato: {spec['type']}")


def build_features_model(contract: dict[str, Any]) -> type[BaseModel]:
    fields = {spec["name"]: _field_for(spec) for spec in contract["features"]}
    return create_model(
        "FlightFeatures",
        __config__=ConfigDict(extra="forbid"),  # campo fora do contrato -> 422
        **fields,
    )


CONTRACT = load_contract()
FEATURE_NAMES: list[str] = [spec["name"] for spec in CONTRACT["features"]]
FlightFeatures = build_features_model(CONTRACT)
