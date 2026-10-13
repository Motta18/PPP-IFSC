"""
Passo 4 - Enviar um arquivo .rnx.gz ao IBGE-PPP via API

Usa headers de navegador para evitar detecção de bot pelo firewall.
"""

import requests
import json
import time
from pathlib import Path

# ========== PARÂMETROS ==========
DATA = "2025-01-15"
JANELA = "meiodia"

BASE = Path(__file__).parent.parent
ARQUIVO_GZ = BASE / "dados/rbmc" / f"{DATA}_{JANELA}" / f"{DATA}_{JANELA}_30s.rnx.gz"

EMAIL = "flamarion.m@aluno.ifsc.edu.br"
MODELO_ANTENA = "TRM159900.00 NONE"
ALTURA_ANTENA = "0.0080"
CODIGO_BDG = "94052"

URL_PPP = "https://servicodados.ibge.gov.br/api/v1/ppp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Origin": "https://ppp.ibge.gov.br",
    "Referer": "https://ppp.ibge.gov.br/",
    "Connection": "keep-alive",
}


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
                r = requests.post(
                    URL_PPP,
                    files=arquivos,
                    data=dados,
                    headers=HEADERS,
                    timeout=300,
                )

            print(f"    Status HTTP: {r.status_code}")
            print(f"    Content-Type: {r.headers.get('Content-Type')}")

            if "html" in r.headers.get("Content-Type", "").lower():
                print("    ⚠ Resposta HTML (firewall):")
                print(f"    {r.text[:300]}")
                raise Exception("Bloqueado pelo firewall")

            return r.json()

        except Exception as e:
            print(f"    Falhou: {e}")
            if tentativa < tentativas:
                print("    Aguardando 60s...")
                time.sleep(60)
            else:
                raise


def main():
    if not ARQUIVO_GZ.exists():
        print(f"ERRO: {ARQUIVO_GZ} não existe.")
        return

    tamanho_kb = ARQUIVO_GZ.stat().st_size / 1024
    print(f"Arquivo: {ARQUIVO_GZ.name}")
    print(f"Tamanho: {tamanho_kb:.1f} KB")
    print()

    print("Enviando ao PPP...")
    resposta = enviar(ARQUIVO_GZ)

    pasta_ppp = BASE / "dados/ppp"
    pasta_ppp.mkdir(parents=True, exist_ok=True)
    arq_resposta = pasta_ppp / f"resposta_{DATA}_{JANELA}.json"

    with open(arq_resposta, "w", encoding="utf-8") as f:
        json.dump(resposta, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Resposta salva em: {arq_resposta}")
    print()
    print(json.dumps(resposta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()