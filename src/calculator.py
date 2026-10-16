"""Lê coordenadas do PPP e do BDG e calcula diferenças em ECEF e ENU."""

import json
import logging
from pathlib import Path

from pyproj import CRS, Transformer


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def converter_dms_para_decimal(dms_str: str) -> float | None:
    """Converte DMS válido em graus decimais ou retorna None se inválido."""
    try:
        partes = dms_str.strip().replace(",", ".").split()
        if len(partes) != 3:
            return None
        graus, minutos, segundos = (float(parte) for parte in partes)
        if not 0 <= minutos < 60 or not 0 <= segundos < 60:
            return None

        sinal = -1.0 if graus < 0 else 1.0
        return sinal * (abs(graus) + minutos / 60 + segundos / 3600)
    except (AttributeError, TypeError, ValueError):
        return None


def _converter_valor_numerico(valor: object, campo: str) -> float:
    """Converte um valor numérico ou uma string com vírgula decimal para float."""
    if valor is None:
        raise ValueError(f"O campo obrigatório {campo!r} está vazio.")
    texto = str(valor).strip().replace(",", ".")
    if texto.endswith(" m"):
        texto = texto[:-2].strip()
    try:
        return float(texto)
    except ValueError as exc:
        raise ValueError(f"O valor do campo {campo!r} não é numérico: {valor!r}.") from exc


def _campo_obrigatorio(dados: dict, chave: str, origem: str) -> object:
    """Retorna um campo obrigatório ou levanta erro com a origem identificada."""
    if chave not in dados:
        raise KeyError(f"O campo obrigatório {chave!r} não existe em {origem}.")
    return dados[chave]


def ler_resultado_ppp(caminho_json: Path) -> dict:
    """Lê o JSON bruto do PPP e normaliza as coordenadas e precisões do resumo."""
    with Path(caminho_json).open("r", encoding="utf-8") as arquivo_json:
        resposta = json.load(arquivo_json)
    if not isinstance(resposta, dict):
        raise ValueError(f"A resposta PPP em {caminho_json} não é um objeto JSON.")

    resumo = _campo_obrigatorio(resposta, "resumo", str(caminho_json))
    if not isinstance(resumo, dict):
        raise ValueError(f"O campo 'resumo' em {caminho_json} não é um objeto JSON.")

    return {
        "lat": converter_dms_para_decimal(
            str(_campo_obrigatorio(resumo, "LAT", "resumo PPP"))
        ),
        "lon": converter_dms_para_decimal(
            str(_campo_obrigatorio(resumo, "LON", "resumo PPP"))
        ),
        "h": _converter_valor_numerico(
            _campo_obrigatorio(resumo, "HGEO", "resumo PPP"), "HGEO"
        ),
        "arquivo": _campo_obrigatorio(resumo, "RINEX", "resumo PPP"),
        "data_processamento": _campo_obrigatorio(resumo, "PROCES", "resumo PPP"),
        "orbita": _campo_obrigatorio(resumo, "ORBITA", "resumo PPP"),
        "precisao_lat": _converter_valor_numerico(
            _campo_obrigatorio(resumo, "SLAT", "resumo PPP"), "SLAT"
        ),
        "precisao_lon": _converter_valor_numerico(
            _campo_obrigatorio(resumo, "SLON", "resumo PPP"), "SLON"
        ),
        "precisao_h": _converter_valor_numerico(
            _campo_obrigatorio(resumo, "SHGEO", "resumo PPP"), "SHGEO"
        ),
    }


def ler_coordenada_bdg(caminho_json: Path) -> dict:
    """Lê e normaliza latitude, longitude e altitude geométrica do BDG."""
    with Path(caminho_json).open("r", encoding="utf-8") as arquivo_json:
        resposta = json.load(arquivo_json)
    if not isinstance(resposta, dict):
        raise ValueError(f"A resposta BDG em {caminho_json} não é um objeto JSON.")

    campos_obrigatorios = ("latitude", "longitude")
    ausentes = [campo for campo in campos_obrigatorios if campo not in resposta]
    if ausentes:
        raise ValueError(
            f"Campos obrigatórios ausentes na resposta BDG em {caminho_json}: "
            f"{', '.join(ausentes)}."
        )

    return {
        "lat": _converter_valor_numerico(
            resposta["latitude"], "latitude"
        ),
        "lon": _converter_valor_numerico(
            resposta["longitude"], "longitude"
        ),
        "h": _converter_valor_numerico(
            resposta.get("altitudeGeometrica", "0"),
            "altitudeGeometrica",
        ),
        "nome": resposta.get("nomeEstacao", ""),
        "datum": resposta.get("sistemaReferenciaCoordenada", ""),
    }


def geodesica_para_ecef(lat: float, lon: float, h: float) -> tuple[float, float, float]:
    """Converte latitude, longitude e altitude para ECEF SIRGAS2000, em metros."""
    # EPSG:5880 é Brasil Policônica; o CRS geocêntrico SIRGAS2000 correto é EPSG:4988.
    geodesico_3d = CRS.from_epsg(4674).to_3d()
    conversor = Transformer.from_crs(geodesico_3d, "EPSG:4988", always_xy=True)
    x, y, z = conversor.transform(lon, lat, h)
    return float(x), float(y), float(z)


def calcular_diferencas(ppp: dict, bdg: dict) -> dict:
    """Calcula diferenças PPP-BDG em ECEF e no referencial topocêntrico ENU."""
    x_ppp, y_ppp, z_ppp = geodesica_para_ecef(ppp["lat"], ppp["lon"], ppp["h"])
    x_bdg, y_bdg, z_bdg = geodesica_para_ecef(bdg["lat"], bdg["lon"], bdg["h"])

    dx = x_bdg - x_ppp
    dy = y_bdg - y_ppp
    dz = z_bdg - z_ppp

    # A transformação topocêntrica fica ancorada na coordenada oficial do BDG.
    ecef_para_enu = Transformer.from_pipeline(
        "+proj=pipeline "
        "+step +proj=topocentric +ellps=GRS80 "
        f"+lat_0={bdg['lat']} +lon_0={bdg['lon']} +h_0={bdg['h']}"
    )
    leste_ppp, norte_ppp, vertical_ppp = ecef_para_enu.transform(x_ppp, y_ppp, z_ppp)
    leste_bdg, norte_bdg, vertical_bdg = ecef_para_enu.transform(x_bdg, y_bdg, z_bdg)

    de = leste_bdg - leste_ppp
    dn = norte_bdg - norte_ppp
    du = vertical_bdg - vertical_ppp
    dh = bdg["h"] - ppp["h"]

    return {
        "dX": dx,
        "dY": dy,
        "dZ": dz,
        "dE": de,
        "dN": dn,
        "dU": du,
        "dh": dh,
        "distancia_3d": (de**2 + dn**2 + du**2) ** 0.5,
        "lat_ppp": ppp["lat"],
        "lon_ppp": ppp["lon"],
        "h_ppp": ppp["h"],
        "lat_bdg": bdg["lat"],
        "lon_bdg": bdg["lon"],
        "h_bdg": bdg["h"],
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    caminho_ppp = PROJECT_ROOT / "data" / "results_output" / "2503151300A_resposta_bruta.json"
    caminho_bdg = PROJECT_ROOT / "data" / "results_output" / "94052_bdg_resposta_bruta.json"
    caminho_saida = PROJECT_ROOT / "data" / "results_output" / "2503151300A_comparacao.json"

    try:
        resultado_ppp = ler_resultado_ppp(caminho_ppp)
        coordenada_bdg = ler_coordenada_bdg(caminho_bdg)
        diferencas = calcular_diferencas(resultado_ppp, coordenada_bdg)

        print("Componente              Diferença (m)")
        print("--------------------------------------")
        for chave in ("dX", "dY", "dZ", "dE", "dN", "dU", "dh", "distancia_3d"):
            print(f"{chave:<24} {diferencas[chave]:>12.4f}")

        caminho_saida.parent.mkdir(parents=True, exist_ok=True)
        with caminho_saida.open("w", encoding="utf-8") as arquivo_saida:
            json.dump(diferencas, arquivo_saida, indent=2, ensure_ascii=False)
        LOGGER.info("Comparação salva em %s.", caminho_saida)
        print(f"\nComparação salva em: {caminho_saida}")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        LOGGER.exception("Não foi possível calcular a comparação PPP-BDG.")
        print(f"Erro ao comparar as coordenadas: {exc}")
