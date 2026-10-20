"""Modelo de validacao do payload, gerado a partir de schemas/features.json.

O contrato nao e reescrito a mao aqui: o modelo pydantic e montado em tempo de
importacao lendo o JSON, para que API e contrato nunca divirjam.
"""

import json
import os
from pathlib import Path
from typing import Any, Literal, Optional

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
    # nullable: feature pode faltar (ex.: clima sem estacao meteorologica
    # proxima — ver schemas/features.json). Default e
    # obrigatorio, como antes desta extensao.
    nullable = spec.get("nullable", False)
    default = None if nullable else ...

    if spec["type"] == "STRING":
        if "enum" in spec:
            tipo: Any = Literal[tuple(spec["enum"])]
            field = Field(default, description=description)
        else:
            tipo = str
            field = Field(default, description=description, pattern=spec.get("pattern"))
    elif spec["type"] == "INT64":
        # strict: recusa "18" (string) e 18.5 (float) em vez de converter calado
        tipo = int
        field = Field(
            default,
            description=description,
            ge=spec.get("minimum"),
            le=spec.get("maximum"),
            strict=True,
        )
    elif spec["type"] == "FLOAT64":
        tipo = float
        field = Field(
            default,
            description=description,
            ge=spec.get("minimum"),
            le=spec.get("maximum"),
            strict=True,
        )
    else:
        raise ValueError(f"Tipo nao suportado no contrato: {spec['type']}")

    if nullable:
        tipo = Optional[tipo]
    return tipo, field


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
