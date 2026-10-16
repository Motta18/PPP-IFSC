"""Baixa e extrai o pacote ZIP de resultados do processamento IBGE-PPP."""

import json
import logging
from pathlib import Path
import sys
import time
import zipfile

from curl_cffi import requests as curl_requests


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def extrair_link_resposta(caminho_json: Path) -> str:
    """Lê e retorna o link de download presente no JSON bruto do IBGE-PPP."""
    with caminho_json.open("r", encoding="utf-8") as arquivo_json:
        resposta = json.load(arquivo_json)

    if not isinstance(resposta, dict):
        raise ValueError(f"A resposta em {caminho_json} não contém um objeto JSON.")
    if "link" not in resposta:
        raise KeyError(f"O campo obrigatório 'link' não existe em {caminho_json}.")

    link = resposta["link"]
    if not isinstance(link, str) or not link.strip():
        raise ValueError(f"O campo 'link' em {caminho_json} não contém uma URL válida.")
    return link


def baixar_resultado(url: str, diretorio_destino: Path) -> Path:
    """Baixa o ZIP do resultado, reutilizando um arquivo já existente."""
    destino = Path(diretorio_destino)
    destino.mkdir(parents=True, exist_ok=True)

    nome_arquivo = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    if not nome_arquivo:
        raise ValueError(f"A URL não informa o nome do arquivo de resultado: {url}")
    caminho_zip = destino / nome_arquivo
    if caminho_zip.is_file():
        LOGGER.info("ZIP de resultado já existe; download ignorado: %s", caminho_zip)
        return caminho_zip

    LOGGER.info("Iniciando download do resultado PPP: %s", url)
    caminho_temporario = caminho_zip.with_name(caminho_zip.name + ".part")
    try:
        resposta = curl_requests.get(
            url,
            impersonate="chrome120",
            stream=True,
            timeout=120,
            # Desabilita SSL por incompatibilidade do curl_cffi com impersonate;
            # os sites do IBGE são oficiais e confiáveis.
            verify=False,
        )
        if resposta.status_code != 200:
            raise Exception(
                f"Falha ao baixar o resultado PPP: HTTP {resposta.status_code}: "
                f"{resposta.text[:500]}"
            )

        with caminho_temporario.open("wb") as arquivo:
            for bloco in resposta.iter_content(chunk_size=1024 * 64):
                if bloco:
                    arquivo.write(bloco)
        caminho_temporario.replace(caminho_zip)
    except curl_requests.RequestsError as exc:
        try:
            caminho_temporario.unlink(missing_ok=True)
        except OSError:
            LOGGER.exception("Não foi possível remover o download parcial %s", caminho_temporario)
        raise RuntimeError(f"Falha de conexão ao baixar o resultado PPP de {url}: {exc}") from exc
    except OSError as exc:
        try:
            caminho_temporario.unlink(missing_ok=True)
        except OSError:
            LOGGER.exception("Não foi possível remover o download parcial %s", caminho_temporario)
        raise RuntimeError(f"Falha ao salvar o resultado PPP em {caminho_zip}: {exc}") from exc

    tamanho = caminho_zip.stat().st_size
    LOGGER.info("Download concluído: %s bytes salvos em %s", tamanho, caminho_zip)
    return caminho_zip


def extrair_zip(caminho_zip: Path, diretorio_destino: Path) -> list[Path]:
    """Extrai os arquivos do ZIP e retorna os caminhos dos arquivos extraídos."""
    destino = Path(diretorio_destino)
    destino.mkdir(parents=True, exist_ok=True)
    raiz_destino = destino.resolve()

    try:
        with zipfile.ZipFile(caminho_zip, "r") as arquivo_zip:
            membros = arquivo_zip.infolist()
            caminhos_membros: list[Path] = []

            # Valida todos os nomes antes da extração para evitar escrita fora do destino.
            for membro in membros:
                nome_normalizado = membro.filename.replace("\\", "/")
                partes = nome_normalizado.split("/")
                caminho_membro = Path(*partes)
                caminho_final = (destino / caminho_membro).resolve()
                if (
                    caminho_membro.is_absolute()
                    or any(parte == ".." for parte in partes)
                    or (partes and ":" in partes[0])
                    or not caminho_final.is_relative_to(raiz_destino)
                ):
                    raise ValueError(
                        f"O ZIP contém um caminho de arquivo inseguro: {membro.filename}"
                    )
                caminhos_membros.append(caminho_final)

            caminhos_extraidos: list[Path] = []
            for membro, caminho_final in zip(membros, caminhos_membros):
                arquivo_zip.extract(membro, destino)
                if not membro.is_dir():
                    caminhos_extraidos.append(caminho_final)
                    LOGGER.info("Arquivo extraído: %s", caminho_final)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"O arquivo ZIP está corrompido ou é inválido: {caminho_zip}") from exc

    return caminhos_extraidos


def baixar_e_extrair_lote(
    caminho_historico: Path,
    diretorio_saida: Path,
) -> list[dict]:
    """Baixa e extrai sequencialmente os resultados PPP com status OK do histórico."""
    with Path(caminho_historico).open("r", encoding="utf-8") as arquivo_historico:
        historico = json.load(arquivo_historico)
    if not isinstance(historico, list):
        raise ValueError(f"O histórico em {caminho_historico} deve conter uma lista JSON.")

    entradas_validas: list[dict] = []
    for indice, entrada in enumerate(historico):
        if not isinstance(entrada, dict):
            raise ValueError(
                f"A entrada de índice {indice} no histórico não é um objeto JSON."
            )
        if entrada.get("status") != "OK":
            LOGGER.info(
                "Ignorando %s: status diferente de OK (%s).",
                entrada.get("nome_arquivo", f"entrada {indice}"),
                entrada.get("status"),
            )
            continue
        entradas_validas.append(entrada)

    resultados: list[dict] = []
    saida = Path(diretorio_saida)
    for indice, entrada in enumerate(entradas_validas):
        nome_arquivo = entrada.get("nome_arquivo")
        link = entrada.get("link")
        if not isinstance(nome_arquivo, str) or not nome_arquivo.strip():
            raise ValueError(f"Entrada OK de índice {indice} não contém nome_arquivo válido.")
        nome_base = Path(nome_arquivo).stem
        pasta_extraida = saida / f"{nome_base}_resultado"
        caminho_zip: Path | None = None
        arquivos_extraidos: list[Path] = []

        LOGGER.info(
            "Processando resultado %s (%s de %s).",
            nome_arquivo,
            indice + 1,
            len(entradas_validas),
        )
        try:
            if not isinstance(link, str) or not link.strip():
                raise ValueError(f"A entrada OK de {nome_arquivo} não contém um link válido.")
            caminho_zip = baixar_resultado(link, saida)
            arquivos_extraidos = extrair_zip(caminho_zip, pasta_extraida)
            resultado = {
                "nome_arquivo": nome_arquivo,
                "caminho_zip": str(caminho_zip),
                "caminho_pasta_extraida": str(pasta_extraida),
                "arquivos_extraidos": [str(caminho) for caminho in arquivos_extraidos],
                "status": "OK",
            }
            LOGGER.info(
                "Concluído %s: ZIP em %s; extraídos %s arquivos.",
                nome_arquivo,
                caminho_zip,
                len(arquivos_extraidos),
            )
        except Exception as exc:
            LOGGER.exception("Falha ao baixar ou extrair o resultado de %s.", nome_arquivo)
            resultado = {
                "nome_arquivo": nome_arquivo,
                "caminho_zip": str(caminho_zip) if caminho_zip else None,
                "caminho_pasta_extraida": str(pasta_extraida),
                "arquivos_extraidos": [str(caminho) for caminho in arquivos_extraidos],
                "status": "erro",
                "erro": str(exc),
            }
        resultados.append(resultado)

        if indice < len(entradas_validas) - 1:
            time.sleep(2)

    return resultados


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    diretorio_resultados = PROJECT_ROOT / "data" / "results_output"
    caminho_json = diretorio_resultados / "2503151300A_resposta_bruta.json"
    diretorio_extracao = diretorio_resultados / "2503151300A_resultado"

    try:
        if "--lote" in sys.argv:
            caminho_historico = diretorio_resultados / "historico_processamentos.json"
            resultados_lote = baixar_e_extrair_lote(
                caminho_historico,
                diretorio_resultados,
            )
            zip_baixados = sum(
                1 for resultado in resultados_lote if resultado.get("caminho_zip")
            )
            zip_extraidos = sum(
                1 for resultado in resultados_lote if resultado.get("status") == "OK"
            )
            print(f"ZIPs baixados: {zip_baixados}")
            print(f"ZIPs extraídos: {zip_extraidos}")
            for resultado in resultados_lote:
                print(f"\n{resultado['nome_arquivo']}:")
                for arquivo in resultado["arquivos_extraidos"]:
                    print(f"  {arquivo}")
                if resultado.get("erro"):
                    print(f"  Erro: {resultado['erro']}")
        else:
            link_resultado = extrair_link_resposta(caminho_json)
            caminho_zip = baixar_resultado(link_resultado, diretorio_resultados)
            arquivos_extraidos = extrair_zip(caminho_zip, diretorio_extracao)
            for caminho in arquivos_extraidos:
                print(f"{caminho.name}: {caminho.stat().st_size} bytes")
    except Exception as exc:
        LOGGER.exception("Não foi possível baixar e extrair os resultados PPP.")
        print(f"Erro ao obter os resultados: {exc}")
