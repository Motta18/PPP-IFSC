"""Envia arquivos RINEX ao serviço oficial IBGE-PPP e armazena respostas brutas."""
# Usa requests porque o endpoint PPP não tem Cloudflare. verify=False é necessário
# porque o certificado raiz não está disponível nesta máquina. O curl_cffi continua
# nos módulos rbmc_downloader e results_handler, que acessam endpoints protegidos.

from datetime import datetime
import json
import logging
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


LOGGER = logging.getLogger(__name__)
ENDPOINT_PPP = "https://servicodados.ibge.gov.br/api/v1/ppp"
TAMANHO_MAXIMO_ARQUIVO = 10 * 1024 * 1024
RAIZ_PROJETO = Path(__file__).resolve().parents[1]


def validar_arquivo(caminho: Path) -> None:
    """Valida existência, extensão aceita e limite de tamanho do arquivo RINEX."""
    if not caminho.exists():
        raise ValueError(f"O arquivo não existe: {caminho}")
    if not caminho.is_file():
        raise ValueError(f"O caminho informado não é um arquivo: {caminho}")

    extensao = caminho.suffix.lower()
    extensoes_aceitas = {".rnx", ".crx", ".obs", ".zip", ".tar", ".tgz", ".gz", ".7z"}
    extensoes_aceitas.update(
        f".{ano:02d}o" for ano in range(100)
    )
    extensoes_aceitas.update(
        f".{ano:02d}d" for ano in range(5, 27)
    )
    if extensao not in extensoes_aceitas:
        raise ValueError(
            f"Extensão não aceita para processamento PPP: {extensao or '(sem extensão)'}. "
            "Use .rnx, .crx, .obs, .00o a .99o, .05d a .26d, "
            ".zip, .tar, .tgz, .gz ou .7z."
        )

    tamanho = caminho.stat().st_size
    if tamanho > TAMANHO_MAXIMO_ARQUIVO:
        raise ValueError(
            f"O arquivo tem {tamanho} bytes e excede o limite de "
            f"{TAMANHO_MAXIMO_ARQUIVO} bytes (10 MB): {caminho}"
        )


def enviar_arquivo(caminho_arquivo, email, tipo_levantamento="estatico", modelo_antena="TRM57971.00", altura_antena=0.0081):
    """Envia um arquivo RINEX ao serviço IBGE-PPP e retorna a resposta JSON."""
    validar_arquivo(caminho_arquivo)

    url = "https://servicodados.ibge.gov.br/api/v1/ppp"

    data = {
        "tipo-levantamento": tipo_levantamento,
        "modelo-antena": modelo_antena,
        "altura-antena": str(altura_antena),
        "email": email,
        "autorizacao-uso": "true",
    }

    inicio = datetime.now()
    logging.info(f"Enviando {caminho_arquivo.name} ao IBGE-PPP...")

    try:
        with open(caminho_arquivo, "rb") as f:
            files = {"arquivo": (caminho_arquivo.name, f, "application/octet-stream")}
            resposta = requests.post(url, files=files, data=data, verify=False, timeout=120)
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de rede ao enviar {caminho_arquivo.name}: {e}")
        raise RuntimeError(f"Falha de comunicação com o IBGE-PPP: {e}") from e

    duracao = (datetime.now() - inicio).total_seconds()
    logging.info(f"Resposta do IBGE-PPP para {caminho_arquivo.name}: HTTP {resposta.status_code} em {duracao:.2f}s")

    if resposta.status_code != 200:
        raise RuntimeError(f"Falha ao enviar ao IBGE-PPP: HTTP {resposta.status_code}: {resposta.text[:500]}")

    try:
        return resposta.json()
    except ValueError as e:
        raise RuntimeError(f"Resposta do IBGE-PPP não é JSON válido: {resposta.text[:500]}") from e


def salvar_resposta_bruta(
    resposta: dict,
    nome_base: str,
    diretorio_saida: str = "data/results_output/",
) -> Path:
    """Salva o JSON completo retornado pelo serviço sem extrair ou alterar dados."""
    diretorio = Path(diretorio_saida)
    if not diretorio.is_absolute():
        diretorio = RAIZ_PROJETO / diretorio
    diretorio.mkdir(parents=True, exist_ok=True)

    nome_seguro = Path(nome_base).name
    if not nome_seguro:
        raise ValueError("O nome-base do arquivo de resposta não pode ser vazio.")
    caminho_saida = diretorio / f"{nome_seguro}_resposta_bruta.json"
    with caminho_saida.open("w", encoding="utf-8") as arquivo_saida:
        json.dump(resposta, arquivo_saida, indent=2, ensure_ascii=False)
    return caminho_saida


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    arquivo_teste = Path(r"E:\GEO Semetre 3\Programacao_Arthur\ppp-ibge-rbmc\data\rinex_input\bruto\200101\2001011500A\2001011500A.20O")
    email_teste = "Delamotta18@gmail.com"

    try:
        resposta_bruta = enviar_arquivo(arquivo_teste, email_teste)
        caminho_resposta = salvar_resposta_bruta(resposta_bruta, arquivo_teste.stem)
        print(json.dumps(resposta_bruta, indent=2, ensure_ascii=False))
        print(f"Resposta bruta salva em: {caminho_resposta}")
    except Exception as exc:
        LOGGER.exception("Não foi possível concluir o envio de teste ao IBGE-PPP.")
        print(f"Erro ao processar o arquivo de teste: {exc}")
