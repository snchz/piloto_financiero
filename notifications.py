import requests
import db

def enviar_mensaje_telegram(mensaje):
    cfg = db.get_config()
    token = cfg.get("telegram_token")
    chat_id = cfg.get("telegram_chat_id")
    
    if not token or not chat_id:
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"Error enviando mensaje de Telegram: {e}")