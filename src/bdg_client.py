"""Consulta e salva a resposta bruta da coordenada oficial de uma estação no BDG."""

import json
import logging
from pathlib import Path

import requests


LOGGER = logging.getLogger(__name__)
BDG_ENDPOINT = "https://servicodados.ibge.gov.br/api/v1/bdg/estacoes"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def obter_coordenada_oficial(estacao: str) -> dict:
    """Busca no BDG e retorna o JSON completo da estação solicitada."""
    if not estacao.strip():
        raise ValueError("O código da estação não pode ser vazio.")

    url = f"{BDG_ENDPOINT}/{estacao}"
    LOGGER.info("Consultando coordenada oficial da estação %s no BDG.", estacao)
    try:
        resposta = requests.get(url, timeout=60)
    except requests.RequestException as exc:
        LOGGER.exception("Falha de conexão ao consultar o BDG para a estação %s.", estacao)
        raise RuntimeError(
            f"Falha de comunicação com o BDG para a estação {estacao}: {exc}"
        ) from exc

    if resposta.status_code != 200:
        raise Exception(
            f"Falha ao consultar o BDG: HTTP {resposta.status_code}: {resposta.text}"
        )

    try:
        dados = resposta.json()
    except ValueError as exc:
        raise ValueError(
            f"A resposta do BDG para a estação {estacao} não contém JSON válido: "
            f"{resposta.text[:500]}"
        ) from exc

    if dados is None:
        raise ValueError(
            f"A resposta JSON do BDG para a estação {estacao} não pode ser None."
        )
    if not isinstance(dados, list):
        raise ValueError(
            f"A resposta JSON do BDG para a estação {estacao} não é uma lista."
        )
    if not dados:
        raise ValueError(f"Nenhuma estação encontrada no BDG com o código {estacao}.")

    primeira_estacao = dados[0]
    if not isinstance(primeira_estacao, dict):
        raise ValueError(
            f"O primeiro item da resposta do BDG para a estação {estacao} não é um objeto."
        )
    LOGGER.info("Resposta do BDG recebida para a estação %s.", estacao)
    return primeira_estacao


def salvar_resposta_bruta(
    resposta: dict,
    estacao: str,
    diretorio_saida: str = "data/results_output/",
) -> Path:
    """Salva o JSON completo do BDG sem extrair nem modificar campos."""
    diretorio = Path(diretorio_saida)
    if not diretorio.is_absolute():
        diretorio = PROJECT_ROOT / diretorio
    diretorio.mkdir(parents=True, exist_ok=True)

    nome_estacao = Path(estacao).name
    if not nome_estacao:
        raise ValueError("O código da estação não pode ser vazio.")
    caminho_saida = diretorio / f"{nome_estacao}_bdg_resposta_bruta.json"
    with caminho_saida.open("w", encoding="utf-8") as arquivo_saida:
        json.dump(resposta, arquivo_saida, indent=2, ensure_ascii=False)
    LOGGER.info("Resposta bruta do BDG salva em %s.", caminho_saida)
    return caminho_saida


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    estacao_teste = "94052"

    try:
        resposta_bruta = obter_coordenada_oficial(estacao_teste)
        caminho_resposta = salvar_resposta_bruta(resposta_bruta, estacao_teste)
        print(json.dumps(resposta_bruta, indent=2, ensure_ascii=False))
        print(f"Resposta bruta salva em: {caminho_resposta}")
    except Exception as exc:
        LOGGER.exception("Não foi possível obter a coordenada oficial no BDG.")
        print(f"Erro ao consultar o BDG: {exc}")
