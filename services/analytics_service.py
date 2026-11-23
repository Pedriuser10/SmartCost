import json
import logging
import os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

EVENTS_FILE = os.path.join("data", "analytics_events.json")


def registrar_evento(nombre_evento: str, propiedades: dict = None) -> None:
    """
    Registra un evento de telemetría en data/analytics_events.json
    con programación defensiva (try-except) y logging estándar.
    """
    evento = {
        "evento": nombre_evento,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "propiedades": propiedades if propiedades is not None else {}
    }

    try:
        os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)

        if os.path.exists(EVENTS_FILE):
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                try:
                    eventos = json.load(f)
                    if not isinstance(eventos, list):
                        eventos = []
                except json.JSONDecodeError as e:
                    logging.error(f"Archivo JSON corrupto al leer eventos: {e}")
                    eventos = []
        else:
            eventos = []

        eventos.append(evento)

        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(eventos, f, indent=4, ensure_ascii=False)

        logging.info(f"Evento registrado: {nombre_evento}")

    except (IOError, OSError) as e:
        logging.error(f"Error de entrada/salida al guardar el evento '{nombre_evento}': {e}")
    except Exception as e:
        logging.error(f"Error inesperado en analytics_service: {e}")