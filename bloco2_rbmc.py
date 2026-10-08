"""
Bloco 2 - Download de arquivo diário da RBMC

Baixa o arquivo RINEX2 (15s) de uma estação da RBMC para uma data específica.
O endpoint da API recebe o dia corrido do ano (formato ddd).
"""

import requests
from datetime import datetime
from pathlib import Path


def calcular_dia_do_ano(data_str):
    """
    Recebe uma data no formato 'AAAA-MM-DD' e devolve o dia corrido do ano (ddd).
    Ex: '2025-04-25' -> '115'
    """
    data = datetime.strptime(data_str, "%Y-%m-%d")
    return data.strftime("%j")


def baixar_arquivo_rbmc(estacao, data_str, pasta_destino="dados/rbmc"):
    """
    Baixa o arquivo RINEX2 da RBMC e salva na pasta de destino.
    Devolve o caminho do arquivo salvo.
    """
    ano = data_str[:4]
    dia_do_ano = calcular_dia_do_ano(data_str)

    url = f"https://servicodados.ibge.gov.br/api/v1/rbmc/rinex2/{estacao}/{ano}/{dia_do_ano}"
    print(f"Baixando: {url}")

    resposta = requests.get(url, timeout=60)

    if resposta.status_code != 200:
        raise Exception(f"Erro na API: status {resposta.status_code}")

    Path(pasta_destino).mkdir(parents=True, exist_ok=True)

    nome_arquivo = f"{estacao.lower()}{dia_do_ano}.zip"
    caminho = Path(pasta_destino) / nome_arquivo

    with open(caminho, "wb") as f:
        f.write(resposta.content)

    print(f"Salvo em: {caminho}")
    print(f"Tamanho: {len(resposta.content) / 1024:.1f} KB")

    return caminho


if __name__ == "__main__":
    ESTACAO = "IFSC"
    DATA = "2025-04-25"

    caminho = baixar_arquivo_rbmc(ESTACAO, DATA)
    print(f"\nArquivo baixado com sucesso: {caminho}")