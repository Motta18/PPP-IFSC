"""
Passo 3 - Juntar os 16 arquivos .25O num único .rnx com GFZRNX

Percorre as pastas de uma janela, coleta os .25O e junta tudo num .rnx de 4h.
Força o intervalo de amostragem em 15 segundos com -snp 15.
"""

import subprocess
from pathlib import Path

# ========== PARÂMETROS ==========
DATA = "2025-01-15"
JANELA = "meiodia"

PASTA_JANELA = Path("dados/rbmc") / f"{DATA}_{JANELA}"
ARQUIVO_SAIDA = PASTA_JANELA / f"{DATA}_{JANELA}.rnx"

GFZRNX = Path("ferramentas/gfzrnx/gfzrnx.exe").resolve()


def main():
    if not PASTA_JANELA.exists():
        print(f"ERRO: pasta não existe: {PASTA_JANELA}")
        return

    print(f"GFZRNX: {GFZRNX}")
    print(f"GFZRNX existe? {GFZRNX.exists()}")
    print()

    # Coleta todos os .25O das subpastas
    subpastas = sorted([p for p in PASTA_JANELA.iterdir() if p.is_dir()])

    arquivos_o = []
    for pasta in subpastas:
        arqs = list(pasta.glob("*.25O"))
        if arqs:
            arquivos_o.append(arqs[0].resolve())

    print(f"Encontrados {len(arquivos_o)} arquivos .25O")
    print()

    if not arquivos_o:
        print("ERRO: nenhum .25O encontrado. Rode o passo2 primeiro.")
        return

    # Monta o comando
    comando = [str(GFZRNX)]
    for arq in arquivos_o:
        comando += ["-finp", str(arq)]
    comando += ["-fout", str(ARQUIVO_SAIDA.resolve()), "-vo", "2.11", "-snp", "15", "-f"]

    print(f"Executando GFZRNX com {len(arquivos_o)} arquivos...")
    print(f"Saída: {ARQUIVO_SAIDA}")
    print()

    resultado = subprocess.run(comando, capture_output=True, text=True)

    if ARQUIVO_SAIDA.exists():
        tamanho_mb = ARQUIVO_SAIDA.stat().st_size / 1024 / 1024
        print(f"✓ Arquivo criado: {ARQUIVO_SAIDA}")
        print(f"  Tamanho: {tamanho_mb:.2f} MB")
    else:
        print("✗ GFZRNX NÃO criou o arquivo")
        print()
        print("--- STDOUT ---")
        print(resultado.stdout)
        print("--- STDERR ---")
        print(resultado.stderr)


if __name__ == "__main__":
    main()