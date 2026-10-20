import json
import os
import sys
from pathlib import Path

from google.cloud import bigquery

PROJECT_ID = os.environ.get("PROJECT_ID")
DATASET = os.environ.get("DATASET", "tf_anac")
GOLD_TABLE = os.environ.get("GOLD_TABLE", "tb_anac_gold_features_atraso")
COBERTURA_MINIMA = float(os.environ.get("METAR_COBERTURA_MINIMA", "0.90"))
SAIDA = Path(os.environ.get("METAR_ICAO_FILE", "scripts/metar_aerodromos.txt"))

QUERY = """
SELECT sg_icao_origem, COUNT(*) AS voos
FROM `{project}.{dataset}.{tabela}`
GROUP BY sg_icao_origem
ORDER BY voos DESC
"""


def selecionar_aerodromos(linhas: list[bigquery.Row], cobertura_minima: float) -> tuple[list[str], dict]:
    total_voos = sum(linha["voos"] for linha in linhas)
    selecionados = []
    acumulado = 0
    for linha in linhas:
        selecionados.append(linha["sg_icao_origem"])
        acumulado += linha["voos"]
        if acumulado / total_voos >= cobertura_minima:
            break
    resumo = {
        "total_aerodromos_na_gold": len(linhas),
        "aerodromos_selecionados": len(selecionados),
        "total_voos": total_voos,
        "voos_cobertos": acumulado,
        "cobertura_atingida": round(acumulado / total_voos, 4),
        "cobertura_minima_pedida": cobertura_minima,
    }
    return selecionados, resumo


def main() -> int:
    if not PROJECT_ID:
        print("Erro: defina a variavel de ambiente PROJECT_ID.", file=sys.stderr)
        return 1

    client = bigquery.Client(project=PROJECT_ID)
    query = QUERY.format(project=PROJECT_ID, dataset=DATASET, tabela=GOLD_TABLE)
    linhas = list(client.query(query).result())

    if not linhas:
        print(f"Nenhum registro encontrado em {PROJECT_ID}.{DATASET}.{GOLD_TABLE}.", file=sys.stderr)
        return 1

    selecionados, resumo = selecionar_aerodromos(linhas, COBERTURA_MINIMA)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(
        "\n".join(selecionados) + "\n",
        encoding="utf-8",
    )

    manifest_path = SAIDA.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Lista de aerodromos: {SAIDA} ({len(selecionados)} ICAO)")
    print(f"Manifest: {manifest_path}")
    print(
        f"Cobertura: {resumo['cobertura_atingida']:.2%} dos voos "
        f"({resumo['voos_cobertos']}/{resumo['total_voos']}) com "
        f"{resumo['aerodromos_selecionados']}/{resumo['total_aerodromos_na_gold']} aerodromos"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
