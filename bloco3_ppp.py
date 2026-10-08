"""
Bloco 4 - Envio de arquivo RINEX ao IBGE-PPP via API
"""

import requests
import json
from pathlib import Path

# ===== PARÂMETROS =====
ARQUIVO = "dados/rbmc/teste_consecutivo_v2.rnx.gz"
EMAIL = "flamarion.m@aluno.ifsc.edu.br"

MODELO_ANTENA = "TRM159900.00 NONE"
ALTURA_ANTENA = "0.0080"
TIPO_LEVANTAMENTO = "estatico"
MARCO_IBGE = "SAT94052"

URL_PPP = "https://servicodados.ibge.gov.br/api/v1/ppp"


def enviar_ao_ppp(caminho_arquivo):
    print(f"Enviando: {caminho_arquivo}")
    print(f"E-mail: {EMAIL}")
    print(f"Antena: {MODELO_ANTENA}, altura {ALTURA_ANTENA} m")
    print()

    with open(caminho_arquivo, "rb") as f:
        arquivos = {
            "arquivo": (Path(caminho_arquivo).name, f, "application/gzip")
        }
        dados = {
            "tipo-levantamento": TIPO_LEVANTAMENTO,
            "modelo-antena": MODELO_ANTENA,
            "altura-antena": ALTURA_ANTENA,
            "marco-ibge": MARCO_IBGE,
            "email": EMAIL,
            "autorizacao-uso": "true",
        }
        resposta = requests.post(URL_PPP, files=arquivos, data=dados, timeout=120)

    print(f"Status HTTP: {resposta.status_code}")
    return resposta


if __name__ == "__main__":
    resposta = enviar_ao_ppp(ARQUIVO)

    Path("dados/ppp").mkdir(parents=True, exist_ok=True)

    try:
        dados_json = resposta.json()
        caminho_saida = Path("dados/ppp/resposta_teste.json")
        with open(caminho_saida, "w", encoding="utf-8") as f:
            json.dump(dados_json, f, indent=2, ensure_ascii=False)

        print(f"\nResposta salva em: {caminho_saida}")
        print("\n=== Resposta da API ===")
        print(json.dumps(dados_json, indent=2, ensure_ascii=False))
    except Exception as e:
        caminho_saida = Path("dados/ppp/resposta_teste.txt")
        with open(caminho_saida, "w", encoding="utf-8") as f:
            f.write(resposta.text)

        print(f"\nResposta salva em: {caminho_saida}")
        print("\n=== Resposta bruta ===")
        print(resposta.text[:2000])