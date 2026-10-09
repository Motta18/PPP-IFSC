"""
Bloco 1 - API do BDG (Banco de Dados Geodésicos) do IBGE

Objetivo: obter a coordenada oficial da estação IFSC direto da API,
sem digitar nenhum número à mão.

Estação IFSC = código SAT 94052
"""

import requests


# Código da estação no BDG (achado no descritivo oficial)
CODIGO_ESTACAO = "94052"

# Endpoint da API do BDG
URL_BDG = f"https://servicodados.ibge.gov.br/api/v1/bdg/estacoes/{CODIGO_ESTACAO}"


def buscar_coordenada_oficial():
    """
    Chama a API do BDG e devolve um dicionário com a coordenada oficial
    da estação, já com os números convertidos para float.
    """
    print(f"Consultando a API do BDG para a estação {CODIGO_ESTACAO}...")

    resposta = requests.get(URL_BDG, timeout=30)

    # Verifica se a requisição deu certo (código 200)
    if resposta.status_code != 200:
        raise Exception(f"Erro na API: status {resposta.status_code}")

    # A API devolve uma LISTA com um item (a estação)
    dados = resposta.json()

    if not dados:
        raise Exception("A API não devolveu nenhuma estação.")

    estacao = dados[0]

    # Extrai os campos que interessam
    coordenada = {
        "codigo": estacao["codigoEstacao"],
        "nome": estacao["nomeEstacao"],
        "latitude": estacao["latitude"],              # já em decimal
        "longitude": estacao["longitude"],            # já em decimal
        "altitude": float(estacao["altitudeGeometrica"].replace(",", ".")),  # string -> float
        "latitude_gms": estacao["latitudeGMS"],
        "longitude_gms": estacao["longitudeGMS"],
        "sigma_lat": float(estacao["sigmaLatitude"].replace(",", ".")),
        "sigma_lon": float(estacao["sigmaLongitude"].replace(",", ".")),
        "sigma_alt": float(estacao["sigmaAltitudeGeometrica"].replace(",", ".")),
        "sistema": estacao["sistemaReferenciaCoordenada"],
        "municipio": estacao["municipio"]["nomeMunicipio"],
        "uf": estacao["municipio"]["uf"]["sigla"],
    }

    return coordenada


# Este bloco só roda se o arquivo for executado direto
if __name__ == "__main__":
    coord = buscar_coordenada_oficial()

    print("\n=== Coordenada oficial da IFSC ===")
    print(f"Código:      {coord['codigo']}")
    print(f"Nome:        {coord['nome']}")
    print(f"Município:   {coord['municipio']} - {coord['uf']}")
    print(f"Sistema:     {coord['sistema']}")
    print(f"\nLatitude:    {coord['latitude']}°")
    print(f"Longitude:   {coord['longitude']}°")
    print(f"Altitude:    {coord['altitude']} m")
    print(f"\nLatitude (GMS):  {coord['latitude_gms']}")
    print(f"Longitude (GMS): {coord['longitude_gms']}")
    print(f"\nSigmas: lat={coord['sigma_lat']} m, lon={coord['sigma_lon']} m, alt={coord['sigma_alt']} m")