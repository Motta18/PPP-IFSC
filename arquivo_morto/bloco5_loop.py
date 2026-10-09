"""
Bloco 5 - Loop nas datas e janelas

Para cada combinação (data × janela), faz o pipeline completo:
baixar -> descompactar -> juntar -> compactar -> enviar ao PPP -> comparar.
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

# Caminhos das ferramentas (ABSOLUTOS)
GFZRNX = Path("ferramentas/gfzrnx/gfzrnx.exe").resolve()
CRX2RNX = Path("ferramentas/RNXCMP_4.2.0_Windows_mingw_64bit/CRX2RNX.exe").resolve()

# URLs
URL_IFSC = "http://sat94052.florianopolis.ifsc.edu.br/SAT94052/RINEXv211/{ano}/{dia}/IFSC/"
URL_PPP = "https://servicodados.ibge.gov.br/api/v1/ppp"
URL_BDG = f"https://servicodados.ibge.gov.br/api/v1/bdg/estacoes/{CODIGO_BDG}"

# Pastas
PASTA_DADOS = Path("dados")
PASTA_RBMC = PASTA_DADOS / "rbmc"
PASTA_PPP = PASTA_DADOS / "ppp"
PASTA_SAIDA = Path("saida")

DELAY = 1.5


# ========== AUXILIARES ==========

def dia_do_ano(data_str):
    return datetime.strptime(data_str, "%Y-%m-%d").strftime("%j")


def ano(data_str):
    return data_str[:4]


def mes_dia(data_str):
    return datetime.strptime(data_str, "%Y-%m-%d").strftime("%y%m%d")


def gerar_lista_horarios(hora_inicio, hora_fim):
    horarios = []
    hora = hora_inicio
    minuto = 0
    while hora < hora_fim:
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


# ========== PIPELINE ==========

def baixar_arquivos(data, janela, pasta):
    pasta.mkdir(parents=True, exist_ok=True)

    dia = dia_do_ano(data)
    yr = ano(data)
    prefixo_data = mes_dia(data)

    horarios = gerar_lista_horarios(
        JANELAS[janela]["inicio"],
        JANELAS[janela]["fim"]
    )

    pastas_baixadas = []

    for hhmm in horarios:
        nome_base = f"{prefixo_data}{hhmm}A"
        pasta_arq = pasta / nome_base

        if pasta_arq.exists() and list(pasta_arq.glob("*.25D")):
            print(f"  Já existe: {nome_base}")
            pastas_baixadas.append(pasta_arq)
            continue

        pasta_arq.mkdir(exist_ok=True)

        url = URL_IFSC.format(ano=yr, dia=dia) + f"{nome_base}.zip"
        print(f"  Baixando: {nome_base}")
        r = requests.get(url, timeout=60)
        r.raise_for_status()

        zip_path = pasta_arq / f"{nome_base}.zip"
        with open(zip_path, "wb") as f:
            f.write(r.content)

        shutil.unpack_archive(str(zip_path), str(pasta_arq), "zip")
        zip_path.unlink()

        pastas_baixadas.append(pasta_arq)
        time.sleep(DELAY)

    return pastas_baixadas


def descompactar_hatanaka(pastas):
    for pasta in pastas:
        arquivos_d = list(pasta.glob("*.25D"))
        if not arquivos_d:
            continue

        arq_d = arquivos_d[0]

        if list(pasta.glob("*.25O")):
            continue

        resultado = subprocess.run(
            [str(CRX2RNX), str(arq_d.resolve())],
            capture_output=True,
            text=True
        )

        if resultado.returncode != 0:
            print(f"    ERRO CRX2RNX: {resultado.stderr}")
        elif not list(pasta.glob("*.25O")):
            print(f"    AVISO: .25O não criado para {arq_d.name}")


def juntar_com_gfzrnx(pastas, arquivo_saida):
    arquivos_o = []
    for pasta in pastas:
        arqs = list(pasta.glob("*.25O"))
        if arqs:
            arquivos_o.append(arqs[0].resolve())

    if not arquivos_o:
        raise Exception("Nenhum arquivo .25O encontrado")

    arquivo_saida = arquivo_saida.resolve()

    comando = [str(GFZRNX)]
    for arq in arquivos_o:
        comando += ["-finp", str(arq)]
    comando += ["-fout", str(arquivo_saida), "-vo", "2.11", "-f"]

    print(f"  Juntando {len(arquivos_o)} arquivos...")
    resultado = subprocess.run(comando, capture_output=True, text=True)

    if not arquivo_saida.exists():
        raise Exception(
            f"GFZRNX falhou:\n"
            f"STDOUT: {resultado.stdout}\n"
            f"STDERR: {resultado.stderr}"
        )


def compactar(arquivo_rnx):
    arquivo_gz = arquivo_rnx.with_suffix(".rnx.gz")
    with open(arquivo_rnx, "rb") as f_in:
        with gzip.open(arquivo_gz, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    return arquivo_gz


def enviar_ao_ppp(arquivo_gz):
    with open(arquivo_gz, "rb") as f:
        arquivos = {"arquivo": (arquivo_gz.name, f, "application/gzip")}
        dados = {
            "tipo-levantamento": "estatico",
            "modelo-antena": MODELO_ANTENA,
            "altura-antena": ALTURA_ANTENA,
            "marco-ibge": f"SAT{CODIGO_BDG}",
            "email": EMAIL,
            "autorizacao-uso": "true",
        }
        r = requests.post(URL_PPP, files=arquivos, data=dados, timeout=180)
    r.raise_for_status()
    return r.json()


# ========== COMPARAÇÃO ==========

def dms_para_decimal(dms_str):
    dms_str = dms_str.replace(",", ".")
    partes = dms_str.split()
    graus, minutos, segundos = float(partes[0]), float(partes[1]), float(partes[2])
    sinal = -1 if graus < 0 else 1
    return sinal * (abs(graus) + minutos / 60 + segundos / 3600)


def extrair_metros(valor_str):
    return float(valor_str.replace(",", ".").replace(" m", "").strip())


def comparar_com_oficial(resposta_json, oficial):
    resumo = resposta_json["resumo"]
    lat_ppp = dms_para_decimal(resumo["LAT"])
    lon_ppp = dms_para_decimal(resumo["LON"])
    alt_ppp = extrair_metros(resumo["HGEO"])

    dif_lat_g = lat_ppp - oficial["lat"]
    dif_lon_g = lon_ppp - oficial["lon"]
    dif_alt = alt_ppp - oficial["alt"]

    dif_lat_m = dif_lat_g * 111320.0
    dif_lon_m = dif_lon_g * 111320.0 * math.cos(math.radians(oficial["lat"]))
    dist_h = math.sqrt(dif_lat_m**2 + dif_lon_m**2)
    dist_3d = math.sqrt(dif_lat_m**2 + dif_lon_m**2 + dif_alt**2)

    return {
        "lat_ppp": lat_ppp, "lon_ppp": lon_ppp, "alt_ppp": alt_ppp,
        "dif_lat_mm": dif_lat_m * 1000,
        "dif_lon_mm": dif_lon_m * 1000,
        "dif_alt_mm": dif_alt * 1000,
        "dist_h_mm": dist_h * 1000,
        "dist_3d_mm": dist_3d * 1000,
        "sigma_lat_mm": extrair_metros(resumo["SLAT"]) * 1000,
        "sigma_lon_mm": extrair_metros(resumo["SLON"]) * 1000,
        "sigma_alt_mm": extrair_metros(resumo["SHGEO"]) * 1000,
        "orbita": resumo["ORBITA"],
        "inicio": resumo["INICIO"],
        "fim": resumo["FIM"],
    }


# ========== MAIN ==========

def main():
    PASTA_PPP.mkdir(parents=True, exist_ok=True)
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    print("Buscando coordenada oficial...")
    oficial = buscar_coordenada_oficial()
    print(f"  Lat: {oficial['lat']}, Lon: {oficial['lon']}, Alt: {oficial['alt']}")
    print()

    resultados = []

    for data in DATAS:
        for janela in JANELAS:
            print(f"\n{'='*60}")
            print(f"Processando: {data} / {janela}")
            print('='*60)

            try:
                pasta_janela = PASTA_RBMC / f"{data}_{janela}"

                print("\n[1/5] Baixando arquivos...")
                pastas = baixar_arquivos(data, janela, pasta_janela)

                print("\n[2/5] Descompactando Hatanaka...")
                descompactar_hatanaka(pastas)

                print("\n[3/5] Juntando com GFZRNX...")
                arquivo_rnx = pasta_janela / f"{data}_{janela}.rnx"
                juntar_com_gfzrnx(pastas, arquivo_rnx)

                print("\n[4/5] Compactando...")
                arquivo_gz = compactar(arquivo_rnx)

                print("\n[5/5] Enviando ao PPP...")
                resposta = enviar_ao_ppp(arquivo_gz)

                arq_resposta = PASTA_PPP / f"resposta_{data}_{janela}.json"
                with open(arq_resposta, "w", encoding="utf-8") as f:
                    json.dump(resposta, f, indent=2, ensure_ascii=False)

                comp = comparar_com_oficial(resposta, oficial)

                resultados.append({
                    "data": data,
                    "janela": janela,
                    **comp
                })

                print(f"\n  ✓ Concluído! Dist 3D: {comp['dist_3d_mm']:.1f} mm")

            except Exception as e:
                print(f"\n  ✗ ERRO: {e}")
                resultados.append({
                    "data": data, "janela": janela,
                    "erro": str(e)
                })

            time.sleep(DELAY)

    csv_path = PASTA_SAIDA / "resultados.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        if resultados:
            writer = csv.DictWriter(f, fieldnames=resultados[0].keys())
            writer.writeheader()
            writer.writerows(resultados)

    print(f"\n\n{'='*60}")
    print(f"CONCLUÍDO! Resultados salvos em: {csv_path}")
    print(f"Total de processamentos: {len(resultados)}")
    print('='*60)


if __name__ == "__main__":
    main()