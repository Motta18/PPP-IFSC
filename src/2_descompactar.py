"""
Passo 2 - Descompactar arquivos Hatanaka (.25D) com CRX2RNX

Percorre as pastas de uma janela e descompacta cada .25D em .25O.
"""

import subprocess
from pathlib import Path

# ========== PARÂMETROS ==========
DATA = "2025-01-15"
JANELA = "meiodia"

PASTA_JANELA = Path("dados/rbmc") / f"{DATA}_{JANELA}"

CRX2RNX = Path("ferramentas/RNXCMP_4.2.0_Windows_mingw_64bit/CRX2RNX.exe").resolve()


def main():
    if not PASTA_JANELA.exists():
        print(f"ERRO: pasta não existe: {PASTA_JANELA}")
        return

    # Lista todas as subpastas (uma por arquivo de 15 min)
    subpastas = sorted([p for p in PASTA_JANELA.iterdir() if p.is_dir()])

    print(f"Descompactando {len(subpastas)} pastas em {PASTA_JANELA}")
    print(f"CRX2RNX: {CRX2RNX}")
    print(f"CRX2RNX existe? {CRX2RNX.exists()}")
    print()

    sucesso = 0
    pulados = 0
    erros = 0

    for i, pasta in enumerate(subpastas, 1):
        arquivos_d = list(pasta.glob("*.25D"))

        if not arquivos_d:
            print(f"  [{i:2d}/{len(subpastas)}] {pasta.name}: sem .25D")
            erros += 1
            continue

        # Já existe o .25O? Pula
        if list(pasta.glob("*.25O")):
            print(f"  [{i:2d}/{len(subpastas)}] {pasta.name}: já tem .25O")
            pulados += 1
            continue

        arq_d = arquivos_d[0]

        resultado = subprocess.run(
            [str(CRX2RNX), str(arq_d.resolve())],
            capture_output=True,
            text=True
        )

        if resultado.returncode != 0:
            print(f"  [{i:2d}/{len(subpastas)}] {pasta.name}: ERRO")
            print(f"       {resultado.stderr.strip()}")
            erros += 1
        elif list(pasta.glob("*.25O")):
            print(f"  [{i:2d}/{len(subpastas)}] {pasta.name}: OK")
            sucesso += 1
        else:
            print(f"  [{i:2d}/{len(subpastas)}] {pasta.name}: .25O não criado")
            erros += 1

    print()
    print(f"Resumo: {sucesso} descompactados, {pulados} pulados, {erros} erros")


if __name__ == "__main__":
    main()