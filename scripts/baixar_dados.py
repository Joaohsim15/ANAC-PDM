import requests, pathlib

destino = pathlib.Path("vra")
destino.mkdir(exist_ok=True)

for ano in range(2000, 2027):
    for mes in range(1, 13):
        if ano <= 2009:
            nome = f"VRA_{ano}{mes}.csv"        # ex: VRA_20001.csv, VRA_200010.csv
        else:
            nome = f"VRA_{ano}_{mes:02d}.csv"   # ex: VRA_2010_01.csv
        url = f"https://siros.anac.gov.br/siros/registros/diversos/vra/{ano}/{nome}"
        r = requests.get(url, timeout=120)
        if r.status_code == 200:
            # salva sempre com nome padronizado, para facilitar depois
            (destino / f"VRA_{ano}_{mes:02d}.csv").write_bytes(r.content)
            print("ok", ano, mes)
        else:
            print("não encontrado:", url)