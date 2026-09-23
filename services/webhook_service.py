import os
import threading
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from utils.logger import get_logger

load_dotenv()

log = get_logger("webhook")

_TIMEOUT = 5.0


def disparar_evento(evento: str, dados: dict) -> None:
    """
    Notifica o Laravel de um evento ocorrido no banco (fire-and-forget).

    Não bloqueia o chamador nem propaga exceção: se LARAVEL_WEBHOOK_URL não
    estiver configurada (Laravel ainda não existe) ou o envio falhar, apenas
    loga e segue — os robôs nunca podem quebrar por causa disso.
    """
    url = os.getenv("LARAVEL_WEBHOOK_URL")
    if not url:
        return

    thread = threading.Thread(
        target=_enviar, args=(url, evento, dados), daemon=True
    )
    thread.start()


def _enviar(url: str, evento: str, dados: dict) -> None:
    token = os.getenv("LARAVEL_WEBHOOK_TOKEN")

    payload = {
        "event": evento,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": dados,
    }

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        httpx.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
    except Exception as e:
        log.warning(f"Falha ao enviar webhook '{evento}': {e}")
