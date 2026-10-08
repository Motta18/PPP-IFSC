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
from datetime import datetime, timedelta
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

# Janelas em UTC
JANELAS = {
    "meiodia": {"inicio": 13, "fim": 17},    # 13:00-17:00 UTC
    "meianoite": {"inicio": 1, "fim": 5},    # 01:00-05:00 UTC
}

# Caminhos das ferramentas
GFZRNX = Path("ferramentas/gfzrnx/gfzrnx.exe")
CRX2RNX = Path("ferramentas/RNXCMP_4.2.0_Windows_mingw_64bit/CRX2RNX.exe")

# URLs
URL_IFSC = "http://sat94052.florianopolis.ifsc.edu.br/SAT94052/RINEXv211/{ano}/{dia}/IFSC/"
URL_PPP = "https://servicodados.ibge.gov.br/api/v1/ppp"
URL_BDG = f"https://servicodados.ibge.gov.br/api/v1/bdg/estacoes/{CODIGO_BDG}"

# Pasta raiz dos dados
PASTA_DADOS = Path("dados")
PASTA_RBMC = PASTA_DADOS / "rbmc"
PASTA_PPP = PASTA_DADOS / "ppp"
PASTA_SAIDA = Path("saida")

# Delay entre requisições (regra do trabalho)
DELAY = 1.5


# ========== FUNÇÕES AUXILIARES ==========

def dia_do_ano(data_str):
    """'2025-01-15' -> '015'"""
    return datetime.strptime(data_str, "%Y-%m-%d").strftime("%j")


def ano(data_str):
    return data_str[:4]


def mes_dia(data_str):
    """'2025-01-15' -> '250115' (formato dos arquivos do IFSC)"""
    return datetime.strptime(data_str, "%Y-%m-%d").strftime("%y%m%d")


def gerar_lista_horarios(hora_inicio, hora_fim):
    """
    Gera lista de horários de 15 em 15 min entre hora_inicio e hora_fim.
    Ex: (13, 17) -> ['1300', '1315', ..., '1645']
    """
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
    """Retorna a coordenada oficial da estação (API BDG)."""
    resposta = requests.get(URL_BDG, timeout=30)
    resposta.raise_for_status()
    est = resposta.json()[0]
    return {
        "lat": est["latitude"],
        "lon": est["longitude"],
        "alt": float(est["altitudeGeometrica"].replace(",", ".")),
    }


# ========== PIPELINE ==========

def baixar_arquivos(data, janela, pasta):
    """Baixa os 16 arquivos da janela."""
    pasta.mkdir(parents=True, exist_ok=True)

    dia = dia_do_ano(data)
    yr = ano(data)
    prefixo_data = mes_dia(data)

    horarios = gerar_lista_horarios(
        JANELAS[janela]["inicio"],
        JANELAS[janela]["fim"]
    )

    arquivos_baixados = []

    for hhmm in horarios:
        nome_base = f"{prefixo_data}{hhmm}A"
        pasta_arq = pasta / nome_base

        # Se já existe, pula
        if pasta_arq.exists() and list(pasta_arq.glob("*.25D")):
            print(f"  Já existe: {nome_base}")
            arquivos_baixados.append(pasta_arq)
            continue

        pasta_arq.mkdir(exist_ok=True)

        # Baixa o ZIP
        url = URL_IFSC.format(ano=yr, dia=dia) + f"{nome_base}.zip"
        print(f"  Baixando: {nome_base}")
        r = requests.get(url, timeout=60)
        r.raise_for_status()

        # Salva e extrai o ZIP
        zip_path = pasta_arq / f"{nome_base}.zip"
        with open(zip_path, "wb") as f:
            f.write(r.content)

        shutil.unpack_archive(str(zip_path), str(pasta_arq), "zip")
        zip_path.unlink()  # Remove o ZIP depois de extrair

        arquivos_baixados.append(pasta_arq)
        time.sleep(DELAY)

    return arquivos_baixados


def descompactar_hatanaka(pastas):
    """Descompacta cada .25D com CRX2RNX."""
    for pasta in pastas:
        arquivos_d = list(pasta.glob("*.25D"))
        if not arquivos_d:
            continue

        arq_d = arquivos_d[0]
        # Se já existe o .25O, pula
        if list(pasta.glob("*.25O")):
            continue

        subprocess.run(
            [str(CRX2RNX), str(arq_d)],
            cwd=str(pasta),
            capture_output=True,
            text=True
        )


def juntar_com_gfzrnx(pastas, arquivo_saida):
    """Junta os .25O de todas as pastas em um .rnx."""
    # Coleta todos os .25O
    arquivos_o = []
    for pasta in pastas:
        arqs = list(pasta.glob("*.25O"))
        if arqs:
            arquivos_o.append(arqs[0])

    if not arquivos_o:
        raise Exception("Nenhum arquivo .25O encontrado")

    # Monta o comando do GFZRNX
    comando = [str(GFZRNX)]
    for arq in arquivos_o:
        comando += ["-finp", str(arq)]
    comando += ["-fout", str(arquivo_saida), "-vo", "2.11", "-f"]

    print(f"  Juntando {len(arquivos_o)} arquivos...")
    resultado = subprocess.run(comando, capture_output=True, text=True)

    if not arquivo_saida.exists():
        raise Exception(f"GFZRNX falhou:\n{resultado.stdout}\n{resultado.stderr}")


def descompactar_hatanaka(pastas):
    """Descompacta cada .25D com CRX2RNX."""
    for pasta in pastas:
        arquivos_d = list(pasta.glob("*.25D"))
        if not arquivos_d:
            continue

        arq_d = arquivos_d[0]

        # Já existe o .25O? Pula
        if list(pasta.glob("*.25O")):
            continue

        # Roda o CRX2RNX com caminho absoluto, SEM cwd
        resultado = subprocess.run(
            [str(CRX2RNX.resolve()), str(arq_d.resolve())],
            capture_output=True,
            text=True
        )

        if resultado.returncode != 0:
            print(f"    ERRO: {resultado.stderr}")
        elif not list(pasta.glob("*.25O")):
            print(f"    AVISO: .25O não criado para {arq_d.name}")


def enviar_ao_ppp(arquivo_gz):
    """Envia o arquivo ao PPP e retorna a resposta JSON."""
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

    import math
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
    import csv

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

                # 1. Baixar
                print("\n[1/5] Baixando arquivos...")
                pastas = baixar_arquivos(data, janela, pasta_janela)

                # 2. Descompactar
                print("\n[2/5] Descompactando Hatanaka...")
                descompactar_hatanaka(pastas)

                # 3. Juntar
                print("\n[3/5] Juntando com GFZRNX...")
                arquivo_rnx = pasta_janela / f"{data}_{janela}.rnx"
                juntar_com_gfzrnx(pastas, arquivo_rnx)

                # 4. Compactar
                print("\n[4/5] Compactando...")
                arquivo_gz = compactar(arquivo_rnx)

                # 5. Enviar
                print("\n[5/5] Enviando ao PPP...")
                resposta = enviar_ao_ppp(arquivo_gz)

                # Salva a resposta bruta
                arq_resposta = PASTA_PPP / f"resposta_{data}_{janela}.json"
                with open(arq_resposta, "w", encoding="utf-8") as f:
                    json.dump(resposta, f, indent=2, ensure_ascii=False)

                # Compara
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

            # Delay entre processamentos
            time.sleep(DELAY)

    # Salva CSV
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