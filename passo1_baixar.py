"""
Passo 1 - Baixar os 16 arquivos de UMA janela do servidor IFSC

Baixa os arquivos de 15 minutos de uma janela de 4h de uma estação.
Testa apenas UMA data e UMA janela.
"""

import requests
import shutil
import time
from datetime import datetime
from pathlib import Path

# ========== PARÂMETROS ==========
ESTACAO = "IFSC"
DATA = "2025-01-15"

# Janela "meiodia" = 13:00-17:00 UTC
# Janela "meianoite" = 01:00-05:00 UTC
JANELA = "meiodia"

HORARIOS = {
    "meiodia": {"inicio": 13, "fim": 17},
    "meianoite": {"inicio": 1, "fim": 5},
}

URL_IFSC = "http://sat94052.florianopolis.ifsc.edu.br/SAT94052/RINEXv211/{ano}/{dia}/IFSC/"
PASTA_DESTINO = Path("dados/rbmc") / f"{DATA}_{JANELA}"
DELAY = 1.5


def dia_do_ano(data_str):
    return datetime.strptime(data_str, "%Y-%m-%d").strftime("%j")


def mes_dia(data_str):
    return datetime.strptime(data_str, "%Y-%m-%d").strftime("%y%m%d")


def gerar_lista_horarios(inicio, fim):
    horarios = []
    hora, minuto = inicio, 0
    while hora < fim:
        horarios.append(f"{hora:02d}{minuto:02d}")
        minuto += 15
        if minuto == 60:
            minuto = 0
            hora += 1
    return horarios


def main():
    PASTA_DESTINO.mkdir(parents=True, exist_ok=True)

    dia = dia_do_ano(DATA)
    ano = DATA[:4]
    prefixo = mes_dia(DATA)

    horarios = gerar_lista_horarios(
        HORARIOS[JANELA]["inicio"],
        HORARIOS[JANELA]["fim"]
    )

    print(f"Baixando {len(horarios)} arquivos de {DATA} / {JANELA}")
    print(f"Destino: {PASTA_DESTINO}")
    print()

    for i, hhmm in enumerate(horarios, 1):
        nome_base = f"{prefixo}{hhmm}A"
        pasta_arq = PASTA_DESTINO / nome_base

        # Pula se já existe
        if pasta_arq.exists() and list(pasta_arq.glob("*.25D")):
            print(f"  [{i:2d}/{len(horarios)}] Já existe: {nome_base}")
            continue

        pasta_arq.mkdir(exist_ok=True)

        url = URL_IFSC.format(ano=ano, dia=dia) + f"{nome_base}.zip"
        print(f"  [{i:2d}/{len(horarios)}] Baixando: {nome_base}")

        r = requests.get(url, timeout=60)
        r.raise_for_status()

        zip_path = pasta_arq / f"{nome_base}.zip"
        with open(zip_path, "wb") as f:
            f.write(r.content)

        shutil.unpack_archive(str(zip_path), str(pasta_arq), "zip")
        zip_path.unlink()

        time.sleep(DELAY)

    print(f"\n✓ Concluído! Arquivos em: {PASTA_DESTINO}")


if __name__ == "__main__":
    main()