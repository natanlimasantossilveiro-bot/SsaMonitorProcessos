import logging
import os
from logging.handlers import RotatingFileHandler


def configurar_logger(gravar_arquivo: bool = False) -> None:
    """
    Configura o logger raiz do sistema SSA Monitor.
    Deve ser chamado uma vez na inicializacao (main.py).

    Formato: 2026-06-29 10:45:23 [INFO ] modulo               | mensagem
    """
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-5s] %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    raiz = logging.getLogger("ssa")
    raiz.setLevel(logging.DEBUG)

    if raiz.handlers:
        return

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    raiz.addHandler(console)

    if gravar_arquivo:
        os.makedirs("logs", exist_ok=True)
        arquivo = RotatingFileHandler(
            "logs/ssa_monitor.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=7,
            encoding="utf-8",
        )
        arquivo.setLevel(logging.DEBUG)
        arquivo.setFormatter(fmt)
        raiz.addHandler(arquivo)


def get_logger(nome: str) -> logging.Logger:
    """
    Retorna um logger filho com o nome especificado.

    Exemplo:
        from utils.logger import get_logger
        log = get_logger("curitiba")
        log.info("Formulario preenchido com sucesso")
        log.warning("Sitekey nao encontrada - usando fallback")
        log.error("Janela de resultado nao localizada")
    """
    return logging.getLogger(f"ssa.{nome}")