"""
Passo 5 - Comparar a coordenada do PPP com a oficial

Lê o JSON salvo em dados/ppp/ e compara com a coordenada do BDG.
"""

import json
import math
from pathlib import Path

DATA = "2025-01-15"
JANELA = "meiodia"

ARQUIVO_RESPOSTA = Path("dados/ppp") / f"resposta_{DATA}_{JANELA}.json"

OFICIAL = {
    "lat": -27.5944332614,
    "lon": -48.5420833864,
    "alt": 26.473,
}


def dms_para_decimal(dms_str):
    dms_str = dms_str.replace(",", ".")
    partes = dms_str.split()
    graus, minutos, segundos = float(partes[0]), float(partes[1]), float(partes[2])
    sinal = -1 if graus < 0 else 1
    return sinal * (abs(graus) + minutos / 60 + segundos / 3600)


def extrair_metros(valor_str):
    return float(valor_str.replace(",", ".").replace(" m", "").strip())


def comparar(resposta_json, oficial):
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
    }


if __name__ == "__main__":
    with open(ARQUIVO_RESPOSTA, "r", encoding="utf-8") as f:
        resposta = json.load(f)

    r = comparar(resposta, OFICIAL)

    print("=" * 50)
    print(f"PPP vs OFICIAL - {DATA} / {JANELA}")
    print("=" * 50)
    print(f"Δ Latitude:   {r['dif_lat_mm']:+.1f} mm")
    print(f"Δ Longitude:  {r['dif_lon_mm']:+.1f} mm")
    print(f"Δ Altitude:   {r['dif_alt_mm']:+.1f} mm")
    print(f"Dist. horizontal: {r['dist_h_mm']:.1f} mm")
    print(f"Dist. 3D:         {r['dist_3d_mm']:.1f} mm")