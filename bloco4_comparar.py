"""
Bloco 4 - Parsear resposta do PPP e comparar com a coordenada oficial

Lê o JSON de resposta do IBGE-PPP, extrai as coordenadas, converte de DMS
para decimal e calcula a diferença em metros em relação à coordenada oficial.
"""

import json
import math
from pathlib import Path


# Coordenada oficial da IFSC (do Bloco 1)
# Em produção, isso vem da API do BDG. Aqui está fixo para teste.
OFICIAL = {
    "lat": -27.5944332614,
    "lon": -48.5420833864,
    "alt": 26.473,
}


def dms_para_decimal(dms_str):
    """
    Converte uma string DMS como '-27 35 39,9595' para graus decimais.
    Aceita vírgula ou ponto como separador decimal.
    """
    # Troca vírgula por ponto
    dms_str = dms_str.replace(",", ".")

    # Divide em graus, minutos e segundos
    partes = dms_str.split()

    graus = float(partes[0])
    minutos = float(partes[1])
    segundos = float(partes[2])

    # Sinal: se graus for negativo, o resultado todo é negativo
    sinal = -1 if graus < 0 else 1

    decimal = abs(graus) + minutos / 60 + segundos / 3600
    return sinal * decimal


def extrair_metros(valor_str):
    """
    Converte '26,61 m' ou '0,014 m' para float.
    """
    return float(valor_str.replace(",", ".").replace(" m", "").strip())


def comparar(resposta_json, oficial):
    """
    Compara a resposta do PPP com a coordenada oficial.
    Devolve um dicionário com as diferenças em metros.
    """
    resumo = resposta_json["resumo"]

    # Extrai e converte as coordenadas do PPP
    lat_ppp = dms_para_decimal(resumo["LAT"])
    lon_ppp = dms_para_decimal(resumo["LON"])
    alt_ppp = extrair_metros(resumo["HGEO"])

    # Diferenças em graus
    dif_lat_graus = lat_ppp - oficial["lat"]
    dif_lon_graus = lon_ppp - oficial["lon"]
    dif_alt = alt_ppp - oficial["alt"]

    # Converte diferenças de graus para metros
    # 1 grau de latitude ≈ 111.320 m (constante)
    # 1 grau de longitude ≈ 111.320 × cos(latitude)
    metros_por_grau_lat = 111320.0
    metros_por_grau_lon = 111320.0 * math.cos(math.radians(oficial["lat"]))

    dif_lat_m = dif_lat_graus * metros_por_grau_lat
    dif_lon_m = dif_lon_graus * metros_por_grau_lon

    # Distância horizontal total (em metros)
    dist_horizontal = math.sqrt(dif_lat_m**2 + dif_lon_m**2)

    # Distância 3D (incluindo altitude)
    dist_3d = math.sqrt(dif_lat_m**2 + dif_lon_m**2 + dif_alt**2)

    return {
        "lat_ppp": lat_ppp,
        "lon_ppp": lon_ppp,
        "alt_ppp": alt_ppp,
        "dif_lat_m": dif_lat_m,
        "dif_lon_m": dif_lon_m,
        "dif_alt_m": dif_alt,
        "dist_horizontal_m": dist_horizontal,
        "dist_3d_m": dist_3d,
        "sigma_lat_m": extrair_metros(resumo["SLAT"]),
        "sigma_lon_m": extrair_metros(resumo["SLON"]),
        "sigma_alt_m": extrair_metros(resumo["SHGEO"]),
        "orbita": resumo["ORBITA"],
        "inicio": resumo["INICIO"],
        "fim": resumo["FIM"],
    }


if __name__ == "__main__":
    # Lê a resposta do PPP
    caminho_resposta = Path("dados/ppp/resposta_teste.json")
    with open(caminho_resposta, "r", encoding="utf-8") as f:
        resposta = json.load(f)

    # Compara
    resultado = comparar(resposta, OFICIAL)

    # Mostra na tela
    print("=" * 60)
    print("COMPARAÇÃO: PPP vs COORDENADA OFICIAL")
    print("=" * 60)
    print(f"\nEstação: IFSC")
    print(f"Órbita: {resultado['orbita']}")
    print(f"Janela: {resultado['inicio']} → {resultado['fim']}")
    print()
    print("-" * 60)
    print("COORDENADAS")
    print("-" * 60)
    print(f"Latitude  (PPP):  {resultado['lat_ppp']:.10f}°")
    print(f"Latitude  (ofic): {OFICIAL['lat']:.10f}°")
    print(f"Longitude (PPP):  {resultado['lon_ppp']:.10f}°")
    print(f"Longitude (ofic): {OFICIAL['lon']:.10f}°")
    print(f"Altitude  (PPP):  {resultado['alt_ppp']:.3f} m")
    print(f"Altitude  (ofic): {OFICIAL['alt']:.3f} m")
    print()
    print("-" * 60)
    print("DIFERENÇAS")
    print("-" * 60)
    print(f"Δ Latitude:   {resultado['dif_lat_m'] * 1000:+.1f} mm")
    print(f"Δ Longitude:  {resultado['dif_lon_m'] * 1000:+.1f} mm")
    print(f"Δ Altitude:   {resultado['dif_alt_m'] * 1000:+.1f} mm")
    print(f"Dist. horizontal: {resultado['dist_horizontal_m'] * 1000:.1f} mm")
    print(f"Dist. 3D:         {resultado['dist_3d_m'] * 1000:.1f} mm")
    print()
    print("-" * 60)
    print("SIGMAS REPORTADOS PELO PPP")
    print("-" * 60)
    print(f"σ Latitude:   {resultado['sigma_lat_m'] * 1000:.1f} mm")
    print(f"σ Longitude:  {resultado['sigma_lon_m'] * 1000:.1f} mm")
    print(f"σ Altitude:   {resultado['sigma_alt_m'] * 1000:.1f} mm")