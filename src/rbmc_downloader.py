"""
Módulo de download de arquivos RINEX do servidor local da estação IFSC.
Extrai observações RINEX puras e descompacta arquivos Hatanaka/CRINEX (.YYD).

Modos de uso:
1. Como módulo: importar a função baixar() e chamar com parâmetros.
2. Como CLI: python rbmc_downloader.py --estacao IFSC --data 2020-01-01 --horas 15-18
3. Integrado ao config.yaml: o app.py lê o config e chama baixar() para cada entrada.

Flexível: aceita qualquer estação disponível no servidor, qualquer data, e qualquer
conjunto de horas (lista, intervalo ou "todas").
"""

import argparse
import re
import time
import zipfile
from datetime import date
from pathlib import Path
from typing import Iterable

import requests
import urllib3
import yaml

try:
    import hatanaka
except ImportError:
    hatanaka = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# URL base do servidor local do IFSC
SERVIDOR_BASE = "http://sat94052.florianopolis.ifsc.edu.br/SAT94052/RINEXv211"

# Tempo de espera entre downloads (segundos) — regra do trabalho
INTERVALO_ENTRE_DOWNLOADS = 2


def converter_horas(horas_input) -> list[int]:
    """
    Converte diferentes formatos de horas para uma lista de inteiros.

    Aceita:
    - lista de ints: [15, 16, 17, 18]
    - lista de strings: ["15", "16"]
    - string com intervalo: "15-18"
    - string com lista: "15,16,17,18"
    - string "todas" ou "all": 0 a 23
    """
    if isinstance(horas_input, str):
        texto = horas_input.strip().lower()
        if texto in ("todas", "all"):
            return list(range(24))
        if "-" in texto and "," not in texto:
            inicio, fim = texto.split("-")
            return list(range(int(inicio), int(fim) + 1))
        if "," in texto:
            return [int(h.strip()) for h in texto.split(",")]
        return [int(texto)]

    if isinstance(horas_input, Iterable):
        return [int(h) for h in horas_input]

    raise ValueError(f"Formato de horas não reconhecido: {horas_input}")


def listar_arquivos(estacao: str, ano: int, dia_ano: int) -> list[str]:
    """Lista os arquivos .zip disponíveis no servidor para uma estação e dia."""
    url = f"{SERVIDOR_BASE}/{ano}/{dia_ano:03d}/{estacao}/"
    try:
        resposta = requests.get(url, verify=False, timeout=30)
        resposta.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERRO ao acessar {url}: {e}")
        return []

    # Extrai os nomes dos arquivos .zip do HTML
    return sorted(re.findall(r'href="([^"]+\.zip)"', resposta.text))


def baixar_zip(url_pasta: str, nome: str, destino: Path) -> Path | None:
    """Baixa um ZIP do servidor. Pula se já existe. Retorna o caminho ou None em caso de erro."""
    caminho = destino / nome
    if caminho.exists():
        print(f"  {nome} já existe, pulando download")
        return caminho

    try:
        resposta = requests.get(url_pasta + nome, verify=False, timeout=120, stream=True)
        resposta.raise_for_status()
        caminho.write_bytes(resposta.content)
        tamanho_kb = len(resposta.content) // 1024
        print(f"  {nome} baixado ({tamanho_kb} KB)")
        time.sleep(INTERVALO_ENTRE_DOWNLOADS)
        return caminho
    except requests.RequestException as e:
        print(f"  ERRO ao baixar {nome}: {e}")
        return None


def descompactar_hatanaka(caminho: Path) -> Path | None:
    """Descompacta um arquivo Hatanaka (.YYD) para RINEX (.YYo)."""
    if not caminho.is_file():
        print(f"  ERRO: arquivo não encontrado para descompactação: {caminho}")
        return None

    try:
        with caminho.open("r", encoding="ascii", errors="replace") as arquivo:
            primeira_linha = arquivo.readline()
        if "COMPACT RINEX" not in primeira_linha.upper():
            return caminho

        if hatanaka is None:
            print(
                "  ERRO: a biblioteca hatanaka não está instalada. "
                "Instale com: pip install hatanaka"
            )
            return None

        caminho_descompactado = caminho.with_suffix(caminho.suffix[:-1] + "o")
        hatanaka.decompress_on_disk(str(caminho))
        if not caminho_descompactado.is_file():
            raise FileNotFoundError(
                f"o arquivo descompactado esperado não foi criado: {caminho_descompactado}"
            )
        print(f"  Hatanaka descompactado: {caminho_descompactado.name}")
        return caminho_descompactado
    except Exception as exc:
        print(f"  ERRO ao descompactar Hatanaka {caminho.name}: {exc}")
        return None


def extrair_zip(caminho_zip: Path) -> list[Path]:
    """Extrai o ZIP e retorna observações RINEX puras, Hatanaka descompactadas ou .rnx."""
    pasta = caminho_zip.with_suffix("")
    pasta.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(caminho_zip) as z:
            z.extractall(pasta)
        observacoes = []
        for arquivo in pasta.rglob("*"):
            if not arquivo.is_file():
                continue
            extensao = arquivo.suffix
            if re.fullmatch(r"\.\d{2}[Oo]", extensao, re.IGNORECASE):
                observacoes.append(arquivo)
            elif re.fullmatch(r"\.\d{2}[Dd]", extensao, re.IGNORECASE):
                descompactado = descompactar_hatanaka(arquivo)
                if descompactado is not None and descompactado.suffix.lower().endswith("o"):
                    observacoes.append(descompactado)
            elif extensao.lower() == ".rnx":
                observacoes.append(arquivo)
        return sorted(set(observacoes))
    except zipfile.BadZipFile as e:
        print(f"  ERRO: ZIP corrompido {caminho_zip.name}: {e}")
        return []


def baixar(estacao: str, data_str: str, horas, diretorio_base: Path) -> list[Path]:
    """
    Baixa os ZIPs das horas especificadas de um dia e extrai os RINEX.

    Parâmetros:
    - estacao: código da estação (ex.: "IFSC")
    - data_str: data no formato "YYYY-MM-DD"
    - horas: lista de horas, intervalo "15-18", lista "15,16,17", ou "todas"
    - diretorio_base: pasta onde salvar (será criada uma subpasta YYYYMMDD)

    Retorna a lista de caminhos dos arquivos .20O extraídos.
    """
    ano, mes, dia = map(int, data_str.split("-"))
    dia_ano = date(ano, mes, dia).timetuple().tm_yday
    horas_lista = converter_horas(horas)

    pasta_dia = diretorio_base / f"{ano}{mes:02d}{dia:02d}"
    pasta_dia.mkdir(parents=True, exist_ok=True)

    print(f"\n=== {estacao} — {data_str} — horas: {horas_lista} ===")

    url_pasta = f"{SERVIDOR_BASE}/{ano}/{dia_ano:03d}/{estacao}/"
    arquivos = listar_arquivos(estacao, ano, dia_ano)
    if not arquivos:
        print(f"  Nenhum arquivo encontrado para {estacao} em {data_str}")
        return []

    # Filtra apenas os arquivos das horas desejadas
    prefixo_data = f"{ano % 100:02d}{mes:02d}{dia:02d}"
    alvos = [
        a for a in arquivos
        if a.startswith(prefixo_data) and int(a[6:8]) in horas_lista
    ]

    if not alvos:
        print(f"  Nenhum arquivo para as horas {horas_lista} em {data_str}")
        return []

    print(f"  {len(alvos)} arquivo(s) a baixar de {len(arquivos)} disponíveis")

    extraidos = []
    for nome in alvos:
        caminho_zip = baixar_zip(url_pasta, nome, pasta_dia)
        if caminho_zip is None:
            continue
        extraidos.extend(extrair_zip(caminho_zip))

    print(f"  Concluído: {len(extraidos)} arquivo(s) de observação extraído(s)")
    return extraidos


def baixar_do_config(caminho_config: Path, diretorio_base: Path) -> list[Path]:
    """
    Lê o config.yaml e baixa todas as entradas de data/hora configuradas.

    Formato esperado no config.yaml:
    estacao: "IFSC"
    datas:
      - data: "2020-01-01"
        horas: [15, 16, 17, 18]
      - data: "2020-06-21"
        horas: [16, 17, 18, 19]
    """
    with open(caminho_config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    estacao = config.get("estacao", "IFSC")
    datas = config.get("datas", [])

    todos = []
    for entrada in datas:
        if isinstance(entrada, dict):
            data_str = entrada.get("data")
            horas = entrada.get("horas", "todas")
        else:
            # Compatibilidade: lista simples de datas (usa todas as horas)
            data_str = entrada
            horas = "todas"

        if data_str:
            todos.extend(baixar(estacao, data_str, horas, diretorio_base))

    return todos


def main():
    """Ponto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Baixa arquivos RINEX do servidor local da estação IFSC."
    )
    parser.add_argument("--estacao", default="IFSC", help="Código da estação (ex.: IFSC)")
    parser.add_argument("--data", help="Data no formato YYYY-MM-DD")
    parser.add_argument("--horas", default="todas",
                        help="Horas: '15-18', '15,16,17', ou 'todas'")
    parser.add_argument("--config", help="Caminho do config.yaml (ignora --data)")
    parser.add_argument("--destino", default="data/rinex_input/bruto",
                        help="Diretório de destino")

    args = parser.parse_args()
    destino = Path(args.destino)

    if args.config:
        print(f"Lendo configuração de {args.config}")
        extraidos = baixar_do_config(Path(args.config), destino)
    elif args.data:
        extraidos = baixar(args.estacao, args.data, args.horas, destino)
    else:
        parser.error("Informe --data ou --config")

    print(f"\nTotal de arquivos de observação: {len(extraidos)}")


if __name__ == "__main__":
    main()
