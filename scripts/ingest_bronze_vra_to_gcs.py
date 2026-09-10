import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import storage

VRA_DIR = Path(os.environ.get("VRA_LOCAL_DIR", "vra"))
BUCKET_NAME = os.environ.get("GCS_BUCKET")
GCS_PREFIX = os.environ.get("GCS_BRONZE_PREFIX", "bronze/vra/raw").strip("/")
GCS_MANIFEST_PREFIX = os.environ.get("GCS_MANIFEST_PREFIX", "bronze/vra/manifest").strip("/")
ANO_INICIO = int(os.environ.get("VRA_YEAR_START", "2022"))
ANO_FIM = int(os.environ.get("VRA_YEAR_END", "2024"))
MANIFEST_DIR = Path(os.environ.get("MANIFEST_DIR", "manifests"))


def listar_arquivos_no_recorte() -> list[Path]:
    arquivos = []
    for ano in range(ANO_INICIO, ANO_FIM + 1):
        for mes in range(1, 13):
            caminho = VRA_DIR / f"VRA_{ano}_{mes:02d}.csv"
            if caminho.exists():
                arquivos.append(caminho)
    return sorted(arquivos)


def contar_linhas_de_dados(caminho: Path) -> int:
    # Conta em modo binario para nao depender do encoding do arquivo
    # (os CSVs do VRA nao sao UTF-8 puro).
    with caminho.open("rb") as f:
        total_linhas = sum(1 for _ in f)
    return max(total_linhas - 1, 0)  # exclui o cabecalho


def main() -> int:
    if not BUCKET_NAME:
        print("Erro: defina a variavel de ambiente GCS_BUCKET.", file=sys.stderr)
        return 1

    arquivos = listar_arquivos_no_recorte()
    if not arquivos:
        print(
            f"Nenhum arquivo encontrado em {VRA_DIR} para o recorte {ANO_INICIO}-{ANO_FIM}.",
            file=sys.stderr,
        )
        return 1

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    manifest = []
    falhas = 0
    total_linhas = 0

    for caminho in arquivos:
        linhas = contar_linhas_de_dados(caminho)
        tamanho_local = caminho.stat().st_size
        blob_name = f"{GCS_PREFIX}/{caminho.name}"
        blob = bucket.blob(blob_name)

        print(f"Enviando {caminho.name} ({linhas} linhas, {tamanho_local} bytes)...")
        blob.upload_from_filename(str(caminho))
        blob.reload()

        tamanho_confere = blob.size == tamanho_local
        if not tamanho_confere:
            falhas += 1
            print(
                f"  FALHA: tamanho local {tamanho_local} != tamanho no GCS {blob.size}",
                file=sys.stderr,
            )

        total_linhas += linhas
        manifest.append(
            {
                "arquivo": caminho.name,
                "linhas_dados": linhas,
                "tamanho_local_bytes": tamanho_local,
                "gcs_uri": f"gs://{BUCKET_NAME}/{blob_name}",
                "tamanho_gcs_bytes": blob.size,
                "tamanho_confere": tamanho_confere,
                "enviado_em": datetime.now(timezone.utc).isoformat(),
            }
        )

    MANIFEST_DIR.mkdir(exist_ok=True)
    nome_manifest = f"vra_bronze_manifest_{ANO_INICIO}_{ANO_FIM}.json"
    manifest_path = MANIFEST_DIR / nome_manifest
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest_blob = bucket.blob(f"{GCS_MANIFEST_PREFIX}/{nome_manifest}")
    manifest_blob.upload_from_filename(str(manifest_path))

    print()
    print(f"Arquivos enviados: {len(arquivos)}")
    print(f"Total de linhas de dados: {total_linhas}")
    print(f"Manifest local: {manifest_path}")
    print(f"Manifest no GCS: gs://{BUCKET_NAME}/{GCS_MANIFEST_PREFIX}/{nome_manifest}")

    if falhas:
        print(f"\n{falhas} arquivo(s) com tamanho divergente apos upload.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
