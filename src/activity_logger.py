import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def _configurar_logger() -> logging.Logger:
    """Configura um logger que grava em logs/atividade_YYYYMMDD.log."""
    logger = logging.getLogger("atividade")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    arquivo = LOG_DIR / f"atividade_{datetime.now():%Y%m%d}.log"
    handler = logging.FileHandler(arquivo, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger


def registrar(operacao: str, detalhes: str, resultado: str = "OK") -> None:
    """Grava uma linha de log. Ex.: registrar('DOWNLOAD', 'IFSC 2023-05-10 10,14', '8 arquivos')."""
    _configurar_logger().info(f"{operacao} | {detalhes} | {resultado}")
