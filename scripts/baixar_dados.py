import os, pathlib, requests

destino = pathlib.Path(os.environ.get("VRA_LOCAL_DIR", "vra"))
destino.mkdir(exist_ok=True)

# recorte opcional; sem as variaveis, baixa tudo o que o SIROS publica
ano_inicio = int(os.environ.get("VRA_YEAR_START", "2000"))
ano_fim = int(os.environ.get("VRA_YEAR_END", "2026"))

falhas = 0
for ano in range(ano_inicio, ano_fim + 1):
    for mes in range(1, 13):
        if ano <= 2009:
            nome = f"VRA_{ano}{mes}.csv"        # ex: VRA_20001.csv, VRA_200010.csv
        else:
            nome = f"VRA_{ano}_{mes:02d}.csv"   # ex: VRA_2010_01.csv
        url = f"https://siros.anac.gov.br/siros/registros/diversos/vra/{ano}/{nome}"
        r = requests.get(url, timeout=120)
        if r.status_code == 200:
            # HTTP 200 nao prova download completo: confere com o tamanho anunciado
            esperado = r.headers.get("Content-Length")
            if esperado is not None and int(esperado) != len(r.content):
                falhas += 1
                print(f"incompleto: {url} ({len(r.content)} de {esperado} bytes)")
                continue
            # salva sempre com nome padronizado, para facilitar depois
            (destino / f"VRA_{ano}_{mes:02d}.csv").write_bytes(r.content)
            print("ok", ano, mes, len(r.content), "bytes")
        else:
            print("não encontrado:", url)

if falhas:
    raise SystemExit(f"{falhas} arquivo(s) incompleto(s); rode de novo")
