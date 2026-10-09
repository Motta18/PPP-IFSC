"""
Passo 4 - Enviar um arquivo .rnx.gz ao IBGE-PPP via API
"""

import requests
import json
import time
from pathlib import Path

# ========== PARÂMETROS ==========
DATA = "2025-01-15"
JANELA = "meiodia"

ARQUIVO_GZ = Path("dados/rbmc") / f"{DATA}_{JANELA}" / f"{DATA}_{JANELA}_30s.rnx.gz"

EMAIL = "flamarion.m@aluno.ifsc.edu.br"
MODELO_ANTENA = "TRM159900.00 NONE"
ALTURA_ANTENA = "0.0080"
CODIGO_BDG = "94052"

URL_PPP = "https://servicodados.ibge.gov.br/api/v1/ppp"


def enviar(arquivo_gz, tentativas=3):
    for tentativa in range(1, tentativas + 1):
        try:
            print(f"  Tentativa {tentativa}/{tentativas}...")
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
                r = requests.post(URL_PPP, files=arquivos, data=dados, timeout=300)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"    Falhou: {e}")
            if tentativa < tentativas:
                print("    Aguardando 30s...")
                time.sleep(30)
            else:
                raise


def main():
    if not ARQUIVO_GZ.exists():
        print(f"ERRO: {ARQUIVO_GZ} não existe.")
        return

    tamanho_kb = ARQUIVO_GZ.stat().st_size / 1024
    print(f"Arquivo: {ARQUIVO_GZ}")
    print(f"Tamanho: {tamanho_kb:.1f} KB")
    print()

    print("Enviando ao PPP...")
    resposta = enviar(ARQUIVO_GZ)

    # Salva a resposta
    pasta_ppp = Path("dados/ppp")
    pasta_ppp.mkdir(parents=True, exist_ok=True)
    arq_resposta = pasta_ppp / f"resposta_{DATA}_{JANELA}.json"

    with open(arq_resposta, "w", encoding="utf-8") as f:
        json.dump(resposta, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Resposta salva em: {arq_resposta}")
    print()
    print("=== Resposta da API ===")
    print(json.dumps(resposta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()