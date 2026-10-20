import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

GEOJSON_URL = os.environ.get(
    "METAR_GEOJSON_URL",
    "https://mesonet.agron.iastate.edu/geojson/network/BR__ASOS.geojson",
)
ASOS_URL = os.environ.get("METAR_ASOS_URL", "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py")
DESTINO = Path(os.environ.get("METAR_LOCAL_DIR", "metar"))
ANO_INICIO = int(os.environ.get("METAR_YEAR_START", "2016"))
ANO_FIM = int(os.environ.get("METAR_YEAR_END", "2024"))
SLEEP_SEGUNDOS = float(os.environ.get("METAR_SLEEP_SEGUNDOS", "1.0"))
MAX_TENTATIVAS = int(os.environ.get("METAR_MAX_TENTATIVAS", "3"))
FORCAR = os.environ.get("METAR_FORCAR", "0") == "1"


def buscar_estacoes() -> list[dict]:
    resp = requests.get(GEOJSON_URL, timeout=60)
    resp.raise_for_status()
    estacoes = []
    for feature in resp.json()["features"]:
        props = feature["properties"]
        estacoes.append(
            {
                "icao": props["sid"],
                "nome": props["sname"],
                "tzname": props["tzname"],
                "archive_begin": props["archive_begin"],
                "archive_end": props["archive_end"],
                "online": props["online"],
            }
        )
    return estacoes


def recorte_cobertura(estacao: dict) -> tuple[date, date] | None:
    """Interseccao entre a cobertura da estacao e [ANO_INICIO, ANO_FIM]."""
    inicio_recorte = date(ANO_INICIO, 1, 1)
    fim_recorte = date(ANO_FIM, 12, 31)

    archive_begin = estacao["archive_begin"]
    inicio = date.fromisoformat(archive_begin[:10]) if archive_begin else inicio_recorte
    archive_end = estacao["archive_end"]
    fim = date.fromisoformat(archive_end[:10]) if archive_end else fim_recorte

    inicio_efetivo = max(inicio, inicio_recorte)
    fim_efetivo = min(fim, fim_recorte)
    if inicio_efetivo > fim_efetivo:
        return None
    return inicio_efetivo, fim_efetivo


def baixar_estacao(icao: str, inicio: date, fim: date) -> dict:
    destino_arquivo = DESTINO / f"{icao}.csv"
    if destino_arquivo.exists() and not FORCAR:
        return {"icao": icao, "status": "ja_existe", "arquivo": str(destino_arquivo)}

    params = {
        "station": icao,
        "data": "all",
        "year1": inicio.year,
        "month1": inicio.month,
        "day1": inicio.day,
        "hour1": 0,
        "minute1": 0,
        "year2": fim.year,
        "month2": fim.month,
        "day2": fim.day,
        "hour2": 23,
        "minute2": 59,
        "tz": "UTC",
        "format": "onlycomma",
        "missing": "null",
        "trace": "null",
        "report_type": 3,
    }

    resp = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resp = requests.get(ASOS_URL, params=params, timeout=120)
        except requests.RequestException as exc:
            # a IEM e publica e sem SLA: timeout/conexao caida em estacoes com
            # historico grande (anos de dados numa chamada so) e esperado, nao
            # motivo para abortar o backfill inteiro — repete como as outras falhas
            print(f"  tentativa {tentativa}/{MAX_TENTATIVAS}: {exc!r} para {icao}", file=sys.stderr)
            time.sleep(SLEEP_SEGUNDOS * tentativa)
            continue
        if resp.status_code == 200:
            break
        print(f"  tentativa {tentativa}/{MAX_TENTATIVAS}: HTTP {resp.status_code} para {icao}", file=sys.stderr)
        time.sleep(SLEEP_SEGUNDOS * tentativa)
    else:
        raise RuntimeError(f"falha ao buscar {icao} apos {MAX_TENTATIVAS} tentativas")

    linhas = resp.text.splitlines()
    registros = max(len(linhas) - 1, 0)  # exclui o cabecalho

    DESTINO.mkdir(exist_ok=True)
    destino_arquivo.write_text(resp.text, encoding="utf-8")

    # HTTP 200 nao e prova de resposta completa (regra 6 do CLAUDE.md) — uma
    # estacao com cobertura no recorte e zero registros e sinal de problema,
    # nao de ausencia legitima de dados.
    status = "vazio" if registros == 0 else "ok"
    return {
        "icao": icao,
        "status": status,
        "registros": registros,
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "arquivo": str(destino_arquivo),
    }


def main() -> int:
    print("Buscando metadados das estacoes (rede BR__ASOS)...")
    estacoes = buscar_estacoes()
    print(f"{len(estacoes)} estacoes na rede BR__ASOS")

    DESTINO.mkdir(exist_ok=True)
    (DESTINO / "estacoes_br_asos.json").write_text(
        json.dumps(estacoes, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = []
    vazios = 0
    sem_cobertura = 0
    erros = 0
    for estacao in estacoes:
        cobertura = recorte_cobertura(estacao)
        if cobertura is None:
            sem_cobertura += 1
            manifest.append({"icao": estacao["icao"], "status": "sem_cobertura_no_recorte"})
            continue

        inicio, fim = cobertura
        print(f"Baixando {estacao['icao']} ({inicio} a {fim})...")
        try:
            resultado = baixar_estacao(estacao["icao"], inicio, fim)
        except RuntimeError as exc:
            # uma estacao com falha persistente nao pode derrubar o backfill
            # das outras ~150 — registra e segue
            erros += 1
            print(f"  ERRO: {exc}", file=sys.stderr)
            manifest.append({"icao": estacao["icao"], "status": "erro", "detalhe": str(exc)})
            time.sleep(SLEEP_SEGUNDOS)
            continue
        manifest.append(resultado)
        if resultado["status"] == "vazio":
            vazios += 1
            print(f"  AVISO: zero registros para {estacao['icao']} no recorte com cobertura esperada", file=sys.stderr)
        time.sleep(SLEEP_SEGUNDOS)

    manifest_path = DESTINO / f"manifest_{ANO_INICIO}_{ANO_FIM}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nManifest: {manifest_path}")
    print(f"Estacoes sem cobertura no recorte {ANO_INICIO}-{ANO_FIM}: {sem_cobertura}/{len(estacoes)}")
    print(f"Estacoes com cobertura mas zero registros (suspeito): {vazios}")
    print(f"Estacoes com erro persistente apos retries: {erros}")
    return 1 if (vazios or erros) else 0


if __name__ == "__main__":
    sys.exit(main())
