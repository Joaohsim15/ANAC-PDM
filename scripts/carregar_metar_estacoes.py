import json
import os
import sys
from pathlib import Path

from google.cloud import bigquery

PROJECT_ID = os.environ.get("PROJECT_ID")
DATASET = os.environ.get("DATASET", "tf_anac")
TABELA = os.environ.get("METAR_ESTACOES_TABELA", "tb_anac_silver_metar_estacoes")
ARQUIVO_ESTACOES = Path(os.environ.get("METAR_LOCAL_DIR", "metar")) / "estacoes_br_asos.json"


def converter(estacao: dict) -> dict:
    return {
        "sg_icao": estacao["icao"],
        "nm_estacao": estacao["nome"],
        "ds_fuso_iana": estacao["tzname"],
        "dt_cobertura_inicio": estacao["archive_begin"][:10] if estacao["archive_begin"] else None,
        "dt_cobertura_fim": estacao["archive_end"][:10] if estacao["archive_end"] else None,
        "bo_ativa": estacao["online"],
    }


def main() -> int:
    if not PROJECT_ID:
        print("Erro: defina a variavel de ambiente PROJECT_ID.", file=sys.stderr)
        return 1
    if not ARQUIVO_ESTACOES.exists():
        print(f"Erro: {ARQUIVO_ESTACOES} nao encontrado. Rode scripts/baixar_metar.py primeiro.", file=sys.stderr)
        return 1

    estacoes = json.loads(ARQUIVO_ESTACOES.read_text(encoding="utf-8"))
    linhas = [converter(e) for e in estacoes]

    client = bigquery.Client(project=PROJECT_ID)
    tabela_id = f"{PROJECT_ID}.{DATASET}.{TABELA}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    job = client.load_table_from_json(linhas, tabela_id, job_config=job_config)
    job.result()

    print(f"Carregadas {len(linhas)} estacoes em {tabela_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
