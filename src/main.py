"""Orquestra o envio sequencial de arquivos RINEX ao serviço IBGE-PPP."""

import json
import logging
from pathlib import Path
import time
from datetime import datetime

if __package__ in {None, ""}:
    from ibge_client import enviar_arquivo, salvar_resposta_bruta
else:
    from .ibge_client import enviar_arquivo, salvar_resposta_bruta


LOGGER = logging.getLogger(__name__)


def processar_lote(
    caminhos: list[Path],
    email: str,
    modelo_antena: str = "TRM57971.00",
    altura_antena: float = 0.0081,
) -> list[dict]:
    """Envia os arquivos em sequência, salva as respostas brutas e registra falhas."""
    resultados: list[dict] = []

    for indice, caminho in enumerate(caminhos):
        hora_envio = datetime.now().isoformat(timespec="seconds")
        LOGGER.info("Enviando %s ao IBGE-PPP às %s.", caminho.name, hora_envio)
        try:
            resposta = enviar_arquivo(
                caminho,
                email,
                "estatico",
                modelo_antena,
                altura_antena,
            )
            salvar_resposta_bruta(resposta, caminho.stem)
            resultado = {
                "nome_arquivo": caminho.name,
                "status": resposta.get("status", "OK"),
                "link": resposta.get("link"),
                "hora_envio": hora_envio,
            }
            LOGGER.info(
                "Arquivo %s processado com status %s.",
                caminho.name,
                resultado["status"],
            )
        except Exception as exc:
            LOGGER.exception("Falha ao enviar ou salvar a resposta de %s.", caminho.name)
            resultado = {
                "nome_arquivo": caminho.name,
                "status": "erro",
                "link": None,
                "hora_envio": hora_envio,
                "erro": str(exc),
            }

        resultados.append(resultado)
        if indice < len(caminhos) - 1:
            # Mantém pelo menos dois segundos entre o início dos envios consecutivos.
            time.sleep(2)

    return resultados


def salvar_historico(resultados: list[dict], caminho_saida: Path) -> None:
    """Salva o histórico completo dos envios em JSON."""
    destino = Path(caminho_saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as arquivo_historico:
        json.dump(resultados, arquivo_historico, indent=2, ensure_ascii=False)
    LOGGER.info("Histórico de processamento salvo em %s.", destino)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    caminhos_arquivos = [
        Path(r"E:\GEO Semetre 3\Programacao_Arthur\ppp-ibge-rbmc\data\rinex_input\bruto\200101\2001011500A\2001011500A.20O"),
        Path(r"E:\GEO Semetre 3\Programacao_Arthur\ppp-ibge-rbmc\data\rinex_input\bruto\200101\2001011600A\2001011600A.20O"),
        Path(r"E:\GEO Semetre 3\Programacao_Arthur\ppp-ibge-rbmc\data\rinex_input\bruto\200101\2001011700A\2001011700A.20O"),
        Path(r"E:\GEO Semetre 3\Programacao_Arthur\ppp-ibge-rbmc\data\rinex_input\bruto\200101\2001011800A\2001011800A.20O"),
        Path(r"E:\GEO Semetre 3\Programacao_Arthur\ppp-ibge-rbmc\data\rinex_input\bruto\200621\2006211600A\2006211600A.20O"),
        Path(r"E:\GEO Semetre 3\Programacao_Arthur\ppp-ibge-rbmc\data\rinex_input\bruto\200621\2006211700A\2006211700A.20O"),
        Path(r"E:\GEO Semetre 3\Programacao_Arthur\ppp-ibge-rbmc\data\rinex_input\bruto\200621\2006211800A\2006211800A.20O"),
        Path(r"E:\GEO Semetre 3\Programacao_Arthur\ppp-ibge-rbmc\data\rinex_input\bruto\200621\2006211900A\2006211900A.20O"),
    ]
    email_usuario = "Delamotta18@gmail.com"
    caminho_historico = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "results_output"
        / "historico_processamentos.json"
    )

    resultados_lote = processar_lote(
        caminhos_arquivos,
        email_usuario,
        modelo_antena="TRM57971.00",
        altura_antena=0.0081,
    )
    salvar_historico(resultados_lote, caminho_historico)

    sucessos = sum(1 for resultado in resultados_lote if resultado["status"] != "erro")
    erros = len(resultados_lote) - sucessos
    print(f"Total de arquivos: {len(resultados_lote)}")
    print(f"Sucessos: {sucessos}")
    print(f"Erros: {erros}")
    print("Links de resultado:")
    for resultado in resultados_lote:
        if resultado.get("link"):
            print(f"- {resultado['nome_arquivo']}: {resultado['link']}")
