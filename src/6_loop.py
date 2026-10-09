"""
Passo 6 - Loop completo nas datas e janelas

Para cada combinação (data × janela), roda o pipeline:
baixar -> descompactar -> juntar -> reamostrar -> compactar -> enviar -> comparar.
Salva tudo num CSV.
"""

import requests
import json
import gzip
import shutil
import subprocess
import time
import math
import csv
from datetime import datetime
from pathlib import Path

# ========== PARÂMETROS ==========
ESTACAO = "IFSC"
CODIGO_BDG = "94052"
EMAIL = "flamarion.m@aluno.ifsc.edu.br"
MODELO_ANTENA = "TRM159900.00 NONE"
ALTURA_ANTENA = "0.0080"

DATAS = [
    "2025-01-15",
    "2025-03-15",
    "2025-05-15",
    "2025-07-15",
    "2025-09-15",
]

JANELAS = {
    "meiodia": {"inicio": 13, "fim": 17},
    "meianoite": {"inicio": 1, "fim": 5},
}

GFZRNX = Path("../ferramentas/gfzrnx/gfzrnx.exe").resolve()
CRX2RNX = Path("../ferramentas/RNXCMP_4.2.0_Windows_mingw_64bit/CRX2RNX.exe").resolve()

URL_IFSC = "http://sat94052.florianopolis.ifsc.edu.br/SAT94052/RINEXv211/{ano}/{dia}/IFSC/"
URL_PPP = "https://servicodados.ibge.gov.br/api/v1/ppp"
URL_BDG = f"https://servicodados.ibge.gov.br/api/v1/bdg/estacoes/{CODIGO_BDG}"

PASTA_RBMC = Path("../dados/rbmc")
PASTA_PPP = Path("../dados/ppp")
PASTA_SAIDA = Path("../saida")

DELAY = 5


def dia_do_ano(data_str):
    return datetime.strptime(data_str, "%Y-%m-%d").strftime("%j")


def mes_dia(data_str):
    return datetime.strptime(data_str, "%Y-%m-%d").strftime("%y%m%d")


def gerar_lista_horarios(inicio, fim):
    horarios = []
    hora, minuto = inicio, 0
    while hora < fim:
        horarios.append(f"{hora:02d}{minuto:02d}")
        minuto += 15
        if minuto == 60:
            minuto = 0
            hora += 1
    return horarios


def buscar_coordenada_oficial():
    r = requests.get(URL_BDG, timeout=30)
    r.raise_for_status()
    est = r.json()[0]
    return {
        "lat": est["latitude"],
        "lon": est["longitude"],
        "alt": float(est["altitudeGeometrica"].replace(",", ".")),
    }


def baixar_arquivos(data, janela, pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    dia = dia_do_ano(data)
    yr = data[:4]
    prefixo = mes_dia(data)
    horarios = gerar_lista_horarios(JANELAS[janela]["inicio"], JANELAS[janela]["fim"])

    pastas = []
    for hhmm in horarios:
        nome = f"{prefixo}{hhmm}A"
        subpasta = pasta / nome
        if subpasta.exists() and list(subpasta.glob("*.25D")):
            pastas.append(subpasta)
            continue
        subpasta.mkdir(exist_ok=True)
        url = URL_IFSC.format(ano=yr, dia=dia) + f"{nome}.zip"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        zip_path = subpasta / f"{nome}.zip"
        with open(zip_path, "wb") as f:
            f.write(r.content)
        shutil.unpack_archive(str(zip_path), str(subpasta), "zip")
        zip_path.unlink()
        pastas.append(subpasta)
        time.sleep(1.5)
    return pastas


def descompactar(pastas):
    for pasta in pastas:
        arqs_d = list(pasta.glob("*.25D"))
        if not arqs_d or list(pasta.glob("*.25O")):
            continue
        subprocess.run([str(CRX2RNX), str(arqs_d[0].resolve())],
                       capture_output=True, text=True)


def juntar(pastas, saida):
    arqs = []
    for p in pastas:
        a = list(p.glob("*.25O"))
        if a:
            arqs.append(a[0].resolve())
    if not arqs:
        raise Exception("Nenhum .25O encontrado")
    cmd = [str(GFZRNX)]
    for a in arqs:
        cmd += ["-finp", str(a)]
    cmd += ["-fout", str(saida.resolve()), "-vo", "2.11", "-f"]
    subprocess.run(cmd, capture_output=True, text=True)


def reamostrar(rnx_origem, rnx_saida):
    cmd = [str(GFZRNX), "-finp", str(rnx_origem.resolve()),
           "-fout", str(rnx_saida.resolve()), "-vo", "2.11", "-smp", "30", "-f"]
    subprocess.run(cmd, capture_output=True, text=True)


def compactar(rnx):
    gz = rnx.with_suffix(".rnx.gz")
    with open(rnx, "rb") as f_in:
        with gzip.open(gz, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    return gz


def enviar(gz):
    for tentativa in range(1, 4):
        try:
            with open(gz, "rb") as f:
                arquivos = {"arquivo": (gz.name, f, "application/gzip")}
                dados = {
                    "tipo-levantamento": "estatico",
                    "modelo-antena": MODELO_ANTENA,
                    "altura-antena": ALTURA_ANTENA,
                    "marco-ibge": f"SAT{CODIGO_BDG}",
                    "email": EMAIL,
                    "autorizacao-uso": "true",
                }
                r = requests.post(URL_PPP, files=arquivos, data=dados, timeout=300)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"    Tentativa {tentativa}/3 falhou: {e}")
            if tentativa < 3:
                time.sleep(60)
            else:
                raise


def dms_decimal(dms):
    dms = dms.replace(",", ".")
    p = dms.split()
    g, m, s = float(p[0]), float(p[1]), float(p[2])
    sinal = -1 if g < 0 else 1
    return sinal * (abs(g) + m / 60 + s / 3600)


def extrair_m(v):
    return float(v.replace(",", ".").replace(" m", "").strip())


def comparar(resp, oficial):
    r = resp["resumo"]
    lat = dms_decimal(r["LAT"])
    lon = dms_decimal(r["LON"])
    alt = extrair_m(r["HGEO"])
    dlat = (lat - oficial["lat"]) * 111320
    dlon = (lon - oficial["lon"]) * 111320 * math.cos(math.radians(oficial["lat"]))
    dalt = alt - oficial["alt"]
    dh = math.sqrt(dlat**2 + dlon**2)
    d3 = math.sqrt(dlat**2 + dlon**2 + dalt**2)
    return {
        "lat_ppp": lat, "lon_ppp": lon, "alt_ppp": alt,
        "dif_lat_mm": dlat * 1000, "dif_lon_mm": dlon * 1000, "dif_alt_mm": dalt * 1000,
        "dist_h_mm": dh * 1000, "dist_3d_mm": d3 * 1000,
        "orbita": r["ORBITA"], "inicio": r["INICIO"], "fim": r["FIM"],
    }


def main():
    PASTA_PPP.mkdir(parents=True, exist_ok=True)
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    print("Buscando coordenada oficial...")
    oficial = buscar_coordenada_oficial()
    print(f"  Lat: {oficial['lat']}, Lon: {oficial['lon']}, Alt: {oficial['alt']}")

    resultados = []

    for data in DATAS:
        for janela in JANELAS:
            print(f"\n{'='*60}")
            print(f"Processando: {data} / {janela}")
            print('='*60)
            try:
                pasta_janela = PASTA_RBMC / f"{data}_{janela}"

                print("[1/6] Baixando...")
                pastas = baixar_arquivos(data, janela, pasta_janela)

                print("[2/6] Descompactando...")
                descompactar(pastas)

                print("[3/6] Juntando...")
                rnx = pasta_janela / f"{data}_{janela}.rnx"
                juntar(pastas, rnx)

                print("[4/6] Reamostrando 30s...")
                rnx30 = pasta_janela / f"{data}_{janela}_30s.rnx"
                reamostrar(rnx, rnx30)

                print("[5/6] Compactando...")
                gz = compactar(rnx30)

                print("[6/6] Enviando ao PPP...")
                resp = enviar(gz)

                arq_resp = PASTA_PPP / f"resposta_{data}_{janela}.json"
                with open(arq_resp, "w", encoding="utf-8") as f:
                    json.dump(resp, f, indent=2, ensure_ascii=False)

                comp = comparar(resp, oficial)
                resultados.append({"data": data, "janela": janela, **comp})

                print(f"  ✓ Dist 3D: {comp['dist_3d_mm']:.1f} mm")

            except Exception as e:
                print(f"  ✗ ERRO: {e}")
                resultados.append({"data": data, "janela": janela, "erro": str(e)})

            time.sleep(DELAY)

    csv_path = PASTA_SAIDA / "resultados.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        if resultados:
            writer = csv.DictWriter(f, fieldnames=resultados[0].keys())
            writer.writeheader()
            writer.writerows(resultados)

    print(f"\n✓ CSV salvo em: {csv_path}")


if __name__ == "__main__":
    main()