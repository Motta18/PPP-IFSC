"""
Passo 7 - Gerar os gráficos a partir do CSV de resultados

Lê saida/resultados.csv e gera 3 gráficos:
1. Distância 3D × data (meio-dia vs meia-noite)
2. Diferenças por componente (Δ lat, Δ lon, Δ alt)
3. Comparação geral meio-dia × meia-noite
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

BASE = Path(__file__).parent.parent
CSV_PATH = BASE / "saida" / "resultados.csv"
SAIDA = BASE / "saida"


def carregar_dados():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CSV não encontrado: {CSV_PATH}\n"
            "Rode o 6_loop.py primeiro."
        )

    dados = {"meiodia": [], "meianoite": []}

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for linha in reader:
            if "erro" in linha and linha["erro"]:
                continue
            janela = linha["janela"]
            if janela not in dados:
                continue
            dados[janela].append({
                "data": datetime.strptime(linha["data"], "%Y-%m-%d"),
                "dist_3d_mm": float(linha["dist_3d_mm"]),
                "dist_h_mm": float(linha["dist_h_mm"]),
                "dif_lat_mm": float(linha["dif_lat_mm"]),
                "dif_lon_mm": float(linha["dif_lon_mm"]),
                "dif_alt_mm": float(linha["dif_alt_mm"]),
            })

    for k in dados:
        dados[k].sort(key=lambda x: x["data"])

    return dados


def grafico_1_distancia(data):
    fig, ax = plt.subplots(figsize=(10, 6))

    for janela, cor, marcador in [
        ("meiodia", "tab:orange", "o"),
        ("meianoite", "tab:blue", "s"),
    ]:
        if not data[janela]:
            continue
        datas = [d["data"] for d in data[janela]]
        vals = [d["dist_3d_mm"] for d in data[janela]]
        ax.plot(datas, vals, marker=marcador, color=cor,
                label=janela.capitalize(), linewidth=2)

    ax.set_xlabel("Data")
    ax.set_ylabel("Distância 3D (mm)")
    ax.set_title("Afastamento do PPP em relação à coordenada oficial")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))

    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_1_distancia_3d.png", dpi=150)
    plt.close(fig)
    print("Salvo: grafico_1_distancia_3d.png")


def grafico_2_componentes(data):
    fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)

    componentes = [
        ("dif_lat_mm", "Δ Latitude (mm)"),
        ("dif_lon_mm", "Δ Longitude (mm)"),
        ("dif_alt_mm", "Δ Altitude (mm)"),
    ]

    for ax, (campo, ylabel) in zip(axes, componentes):
        for janela, cor, marcador in [
            ("meiodia", "tab:orange", "o"),
            ("meianoite", "tab:blue", "s"),
        ]:
            if not data[janela]:
                continue
            datas = [d["data"] for d in data[janela]]
            vals = [d[campo] for d in data[janela]]
            ax.plot(datas, vals, marker=marcador, color=cor,
                    label=janela.capitalize(), linewidth=2)

        ax.set_ylabel(ylabel)
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.grid(True, alpha=0.3)
        ax.legend()

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    axes[0].set_title("Diferenças por componente")

    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_2_componentes.png", dpi=150)
    plt.close(fig)
    print("Salvo: grafico_2_componentes.png")


def grafico_3_barras(data):
    fig, ax = plt.subplots(figsize=(8, 6))

    medias = []
    rotulos = []

    for janela in ["meiodia", "meianoite"]:
        if data[janela]:
            vals = [d["dist_3d_mm"] for d in data[janela]]
            medias.append(sum(vals) / len(vals))
            rotulos.append(janela.capitalize())

    if not medias:
        print("Sem dados pra gráfico 3")
        return

    ax.bar(rotulos, medias, color=["tab:orange", "tab:blue"])
    ax.set_ylabel("Distância 3D média (mm)")
    ax.set_title("Média do afastamento: meio-dia vs meia-noite")
    ax.grid(True, alpha=0.3, axis="y")

    for i, v in enumerate(medias):
        ax.text(i, v, f"{v:.1f} mm", ha="center", va="bottom")

    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_3_media.png", dpi=150)
    plt.close(fig)
    print("Salvo: grafico_3_media.png")


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)

    print("Carregando dados...")
    data = carregar_dados()

    for janela in data:
        print(f"  {janela}: {len(data[janela])} registros")

    if not any(data.values()):
        print("Nenhum dado válido no CSV.")
        return

    print("\nGerando gráficos...")
    grafico_1_distancia(data)
    grafico_2_componentes(data)
    grafico_3_barras(data)

    print(f"\n✓ Gráficos salvos em: {SAIDA}")


if __name__ == "__main__":
    main()