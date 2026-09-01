import logging
from typing import Final, Optional, Dict, Any
import requests
import db

logger: logging.Logger = logging.getLogger(__name__)
TELEGRAM_API_URL: Final[str] = "https://api.telegram.org/bot{token}/sendMessage"


def enviar_mensaje_telegram(mensaje: str) -> bool:
    """Envía una notificación a través de la API de Telegram."""
    cfg: Dict[str, Any] = db.get_config()
    token: Optional[str] = cfg.get("telegram_token")
    chat_id: Optional[str] = cfg.get("telegram_chat_id")

    if not token or not chat_id:
        return False

    url: str = TELEGRAM_API_URL.format(token=token)
    payload: Dict[str, str] = {
        "chat_id": str(chat_id),
        "text": mensaje,
        "parse_mode": "Markdown"
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        return True
    except requests.RequestException as err:
        logger.error("Error al enviar mensaje a Telegram: %s", err)
        return False