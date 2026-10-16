"""Verifica se o servidor local da estação IFSC está acessível e lista arquivos .zip por web scraping.

Este script tenta acessar a estrutura de RINEX disponibilizada pelo servidor da IFSC e
extrai os nomes dos arquivos .zip diretamente do HTML retornado.
"""

import re
import sys

import requests


URL_EXEMPLO = "http://sat94052.florianopolis.ifsc.edu.br/SAT94052/RINEXv211/2020/001/IFSC/"


def main() -> int:
    """Executa a verificação do servidor e imprime os resultados."""
    try:
        # Requisição GET sem verificação de certificado e com timeout definido.
        resposta = requests.get(URL_EXEMPLO, verify=False, timeout=30)

        print(f"Status HTTP: {resposta.status_code}")
        print("Primeiros 500 caracteres da resposta:")
        print((resposta.text[:500] if resposta.text else "<resposta vazia>"))

        # Busca nomes dos arquivos .zip em todo o HTML usando regex.
        padrao_zip = re.compile(r'href=["\']?([^"\'\s>]+\.zip)', re.IGNORECASE)
        arquivos = sorted(set(padrao_zip.findall(resposta.text)))

        print("\nArquivos .zip encontrados:")
        if arquivos:
            for arquivo in arquivos:
                print(f"- {arquivo}")
        else:
            print("Nenhum arquivo .zip encontrado na resposta HTML.")

        print(f"\nQuantidade de arquivos encontrados: {len(arquivos)}")

        if arquivos:
            print(f"SERVIDOR OK - {len(arquivos)} arquivos encontrados")
        else:
            print("SERVIDOR INACESSIVEL ou sem arquivos")

        return 0

    except requests.RequestException as erro:
        print(f"Erro ao acessar o servidor: {erro}")
        print("SERVIDOR INACESSIVEL ou sem arquivos")
        return 1


if __name__ == "__main__":
    sys.exit(main())
