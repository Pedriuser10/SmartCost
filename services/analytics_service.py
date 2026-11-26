"""Telemetría local: registra eventos de uso en <user_data_dir>/datos/analytics_events.json.

- Vive junto a los demás datos persistentes (no en la carpeta del código, que en Android
  se reemplaza al actualizar la app y que además se empaqueta en el APK).
- Se escribe con el guardado atómico de models.rutas, igual que el resto de los datos.
- Guarda como máximo MAX_EVENTOS (los más recientes) para que el archivo no crezca sin límite.
- Nunca registra datos personales: ni nombres de usuario, ni contraseñas, ni correos.
- Nunca interrumpe la app: cualquier fallo queda en el log y el evento se descarta.
"""
import json
import logging
import os
from datetime import datetime

from models import rutas

NOMBRE_ARCHIVO = "analytics_events.json"
MAX_EVENTOS = 1000

log = logging.getLogger(__name__)


def archivo_eventos():
    return os.path.join(rutas.datos_dir(), NOMBRE_ARCHIVO)


def _leer_eventos(ruta):
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            eventos = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.error("Archivo de eventos corrupto, se empieza uno nuevo: %s", e)
        return []
    return eventos if isinstance(eventos, list) else []


def registrar_evento(nombre_evento: str, propiedades: dict = None) -> None:
    """Agrega un evento al archivo de telemetría. No lanza excepciones."""
    evento = {
        "evento": nombre_evento,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "propiedades": dict(propiedades) if propiedades else {},
    }
    try:
        ruta = archivo_eventos()
        eventos = _leer_eventos(ruta)
        eventos.append(evento)
        rutas.escribir_json_atomico(ruta, eventos[-MAX_EVENTOS:])
        log.info("Evento registrado: %s", nombre_evento)
    except rutas.DatosNoDisponibles as e:
        log.warning("Telemetría desactivada, datos no disponibles (%s): %s", nombre_evento, e)
    except Exception as e:  # la telemetría nunca debe romper la app
        log.error("No se pudo guardar el evento '%s': %s", nombre_evento, e)
