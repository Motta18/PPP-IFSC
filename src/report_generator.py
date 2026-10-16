"""Gera tabelas e gráficos comparativos dos resultados PPP e da coordenada BDG."""

from datetime import datetime
import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    from calculator import calcular_diferencas, converter_dms_para_decimal, ler_coordenada_bdg
else:
    from .calculator import calcular_diferencas, converter_dms_para_decimal, ler_coordenada_bdg


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAMPOS_RESUMO_PPP = (
    "RINEX",
    "INICIO",
    "FIM",
    "MODO",
    "ANTENA",
    "ALTANT",
    "LAT",
    "LON",
    "HGEO",
    "SLAT",
    "SLON",
    "SHGEO",
    "ORBITA",
    "DATUM",
    "UTMN",
    "UTME",
)
CAMPOS_NUMERICOS_METROS = {"ALTANT", "HGEO", "SLAT", "SLON", "SHGEO", "UTMN", "UTME"}


def encontrar_resultados(diretorio_base: Path) -> list[Path]:
    """Localiza relatórios PPP de qualquer ano e mantém o mais recente por nome."""
    base = Path(diretorio_base)
    resultados_por_nome = {}
    for caminho in base.rglob("*.txt"):
        if caminho.is_file() and not caminho.name.upper().endswith("_LEIAME.TXT"):
            nome_normalizado = caminho.name.casefold()
            atual = resultados_por_nome.get(nome_normalizado)
            if atual is None or caminho.stat().st_mtime > atual.stat().st_mtime:
                resultados_por_nome[nome_normalizado] = caminho
    return sorted(
        resultados_por_nome.values(),
        key=lambda caminho: (caminho.name.casefold(), caminho.name),
    )


def ler_resumo_ppp(caminho_txt: Path) -> dict:
    """Lê os campos solicitados do resumo textual PPP e normaliza valores numéricos."""
    caminho = Path(caminho_txt)
    encontrados: dict[str, str] = {}
    with caminho.open("r", encoding="utf-8-sig") as arquivo:
        for linha in arquivo:
            partes = linha.strip().split(maxsplit=1)
            if len(partes) != 2:
                continue
            chave, valor = partes
            if chave in CAMPOS_RESUMO_PPP:
                valor = valor.strip()
                if chave in CAMPOS_NUMERICOS_METROS:
                    valor = valor.removesuffix(" m").strip().replace(",", ".")
                encontrados[chave] = valor

    ausentes = [campo for campo in CAMPOS_RESUMO_PPP if campo not in encontrados]
    if ausentes:
        raise ValueError(f"Campos ausentes no resumo PPP {caminho}: {', '.join(ausentes)}")

    latitude = converter_dms_para_decimal(encontrados["LAT"])
    longitude = converter_dms_para_decimal(encontrados["LON"])
    if latitude is None or longitude is None:
        raise ValueError(f"Coordenada inválida no arquivo {caminho.name}")
    encontrados["LAT"] = latitude
    encontrados["LON"] = longitude
    return encontrados


def _converter_data_hora(valor: str, nome_campo: str, origem: Path) -> datetime:
    """Converte data e hora do relatório PPP, incluindo segundos decimais com vírgula."""
    try:
        return datetime.strptime(valor, "%Y/%m/%d %H:%M:%S,%f")
    except ValueError as exc:
        raise ValueError(
            f"Campo {nome_campo} inválido em {origem}: {valor!r}."
        ) from exc


def comparar_todos(resultados: list[Path], coordenada_bdg: dict) -> list[dict]:
    """Compara as coordenadas PPP de cada relatório com a referência oficial do BDG."""
    comparacoes: list[dict] = []
    for caminho_txt in resultados:
        resumo = ler_resumo_ppp(caminho_txt)
        inicio = _converter_data_hora(resumo["INICIO"], "INICIO", caminho_txt)
        fim = _converter_data_hora(resumo["FIM"], "FIM", caminho_txt)
        duracao_min = (fim - inicio).total_seconds() / 60
        if duracao_min < 0:
            raise ValueError(f"O horário FIM antecede INICIO no arquivo {caminho_txt}.")

        ppp = {
            "lat": resumo["LAT"],
            "lon": resumo["LON"],
            "h": float(resumo["HGEO"]),
        }
        diferencas = calcular_diferencas(ppp, coordenada_bdg)
        comparacoes.append(
            {
                "nome_arquivo": resumo["RINEX"],
                "data_inicio": inicio.strftime("%Y-%m-%d"),
                "hora_inicio": inicio.strftime("%H:%M:%S"),
                "duracao_min": duracao_min,
                "lat_ppp": resumo["LAT"],
                "lon_ppp": resumo["LON"],
                "h_ppp": ppp["h"],
                "dE": diferencas["dE"],
                "dN": diferencas["dN"],
                "dU": diferencas["dU"],
                "dX": diferencas["dX"],
                "dY": diferencas["dY"],
                "dZ": diferencas["dZ"],
                "dh": diferencas["dh"],
                "distancia_3d": diferencas["distancia_3d"],
                "slat": float(resumo["SLAT"]),
                "slon": float(resumo["SLON"]),
                "shgeo": float(resumo["SHGEO"]),
            }
        )
    return comparacoes


def salvar_tabela_csv(comparacoes: list[dict], caminho_csv: Path) -> None:
    """Salva a tabela comparativa em CSV usando separador e decimal brasileiros."""
    destino = Path(caminho_csv)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(comparacoes).to_csv(
        destino,
        sep=";",
        decimal=",",
        index=False,
        encoding="utf-8-sig",
    )
    LOGGER.info("Tabela comparativa salva em %s.", destino)


def gerar_graficos(comparacoes: list[dict], diretorio_saida: Path) -> list[Path]:
    """Gera três PNGs: componentes por época, comparação mensal e estatísticas."""
    if not comparacoes:
        raise ValueError("Não há comparações para gerar os gráficos.")

    destino = Path(diretorio_saida)
    destino.mkdir(parents=True, exist_ok=True)
    nomes = [item["nome_arquivo"] for item in comparacoes]
    componentes = ("dE", "dN", "dU")
    x = np.arange(len(nomes))
    largura = 0.25
    cores_componentes = ("#2878B5", "#55A868", "#C44E52")
    arquivos_gerados: list[Path] = []

    figura, eixo = plt.subplots(figsize=(max(10, len(nomes) * 1.2), 6))
    for indice, (componente, cor) in enumerate(zip(componentes, cores_componentes)):
        valores = [item[componente] for item in comparacoes]
        eixo.bar(
            x + (indice - 1) * largura,
            valores,
            largura,
            label=f"{componente} (m)",
            color=cor,
        )
    eixo.set_title("Diferenças ENU por processamento")
    eixo.set_xlabel("Arquivo RINEX")
    eixo.set_ylabel("Diferença (m)")
    eixo.set_xticks(x, nomes, rotation=45, ha="right")
    eixo.axhline(0, color="black", linewidth=0.8)
    eixo.legend()
    figura.tight_layout()
    caminho_grafico = destino / "diferencas_por_processamento.png"
    figura.savefig(caminho_grafico, dpi=150)
    plt.close(figura)
    arquivos_gerados.append(caminho_grafico)

    cores_meses = {"01": "#2878B5", "06": "#E1812C"}
    rotulos_meses = {"01": "Janeiro (200101)", "06": "Junho (200621)"}
    figura, eixos = plt.subplots(3, 1, figsize=(max(10, len(nomes) * 1.2), 10), sharex=True)
    meses = [item["data_inicio"][5:7] for item in comparacoes]
    for eixo, componente in zip(eixos, componentes):
        valores = [item[componente] for item in comparacoes]
        cores = [cores_meses.get(mes, "#999999") for mes in meses]
        eixo.bar(x, valores, color=cores)
        eixo.set_ylabel(f"{componente} (m)")
        eixo.axhline(0, color="black", linewidth=0.8)
        eixo.grid(axis="y", alpha=0.25)
    eixos[0].set_title("Diferenças ENU por mês")
    eixos[-1].set_xticks(x, nomes, rotation=45, ha="right")
    legenda = [
        plt.Rectangle((0, 0), 1, 1, color=cor, label=rotulos_meses[mes])
        for mes, cor in cores_meses.items()
    ]
    eixos[0].legend(handles=legenda)
    figura.tight_layout()
    caminho_grafico = destino / "diferencas_por_mes.png"
    figura.savefig(caminho_grafico, dpi=150)
    plt.close(figura)
    arquivos_gerados.append(caminho_grafico)

    matriz = np.array([[item[componente] for item in comparacoes] for componente in componentes])
    medias = np.mean(matriz, axis=1)
    desvios = np.std(matriz, axis=1)
    rmse = np.sqrt(np.mean(matriz**2, axis=1))
    x_stats = np.arange(len(componentes))
    figura, eixo = plt.subplots(figsize=(9, 6))
    largura_stats = 0.25
    eixo.bar(x_stats - largura_stats, medias, largura_stats, label="Média")
    eixo.bar(x_stats, desvios, largura_stats, label="Desvio-padrão")
    eixo.bar(x_stats + largura_stats, rmse, largura_stats, label="RMSE")
    eixo.set_title(f"Estatísticas gerais ({len(comparacoes)} processamentos)")
    eixo.set_xlabel("Componente")
    eixo.set_ylabel("Valor (m)")
    eixo.set_xticks(x_stats, componentes)
    eixo.axhline(0, color="black", linewidth=0.8)
    eixo.legend()
    figura.tight_layout()
    caminho_grafico = destino / "estatisticas_gerais.png"
    figura.savefig(caminho_grafico, dpi=150)
    plt.close(figura)
    arquivos_gerados.append(caminho_grafico)

    for caminho in arquivos_gerados:
        LOGGER.info("Gráfico salvo em %s.", caminho)
    return arquivos_gerados


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    diretorio_base = PROJECT_ROOT / "data" / "results_output"
    caminho_bdg = diretorio_base / "94052_bdg_resposta_bruta.json"
    caminho_csv = diretorio_base / "comparacao_geral.csv"
    diretorio_graficos = diretorio_base / "graficos"

    try:
        coordenada_bdg = ler_coordenada_bdg(caminho_bdg)
        resultados = encontrar_resultados(diretorio_base)
        if not resultados:
            raise FileNotFoundError(f"Nenhum arquivo de resultado PPP encontrado em {diretorio_base}.")
        comparacoes = comparar_todos(resultados, coordenada_bdg)
        salvar_tabela_csv(comparacoes, caminho_csv)
        caminhos_graficos = gerar_graficos(comparacoes, diretorio_graficos)

        colunas_metros = (
            "h_ppp",
            "dE",
            "dN",
            "dU",
            "dX",
            "dY",
            "dZ",
            "dh",
            "distancia_3d",
            "slat",
            "slon",
            "shgeo",
        )
        colunas_texto = ("nome_arquivo", "data_inicio", "hora_inicio")
        cabecalho = (
            " | ".join(f"{coluna:>20}" for coluna in colunas_texto)
            + " | "
            + " | ".join(f"{coluna + ' (m)':>12}" for coluna in colunas_metros)
        )
        print(cabecalho)
        print("-" * len(cabecalho))
        for item in comparacoes:
            campos_texto = " | ".join(
                f"{str(item[coluna]):>20}" for coluna in colunas_texto
            )
            campos_metros = " | ".join(
                f"{item[coluna]:12.4f}" for coluna in colunas_metros
            )
            print(f"{campos_texto} | {campos_metros}")
        print(f"\nCSV salvo em: {caminho_csv}")
        print("Gráficos salvos:")
        for caminho_grafico in caminhos_graficos:
            print(f"- {caminho_grafico}")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        LOGGER.exception("Não foi possível gerar o relatório comparativo PPP-BDG.")
        print(f"Erro ao gerar relatório: {exc}")
