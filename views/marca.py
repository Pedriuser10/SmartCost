"""Identidad visual de SmartCost: paleta y recursos gráficos.

Azul oscuro de la noche andina, blanco y rojo de la bandera chilena, y el turquesa de
la marca. Los recursos se generan con herramientas/generar_marca.py.
"""
import os

from kivy.utils import get_color_from_hex

RECURSOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recursos", "marca")
FONDO_LOGIN = os.path.join(RECURSOS, "fondo_login.jpg")
LOGO = os.path.join(RECURSOS, "logo.png")
BANDERA_CHILE = os.path.join(RECURSOS, "bandera_chile.png")

AZUL_OSCURO = get_color_from_hex("#0B1F3A")
AZUL_ANDES = get_color_from_hex("#13315C")
TURQUESA = get_color_from_hex("#1BB0A6")          # acento de marca
TURQUESA_OSCURO = get_color_from_hex("#0E7C7B")   # para botones con texto blanco (contraste 4.9:1)
ROJO_CHILE = get_color_from_hex("#D52B1E")
BLANCO = (1, 1, 1, 1)
TEXTO = get_color_from_hex("#1A2433")
TEXTO_SUAVE = get_color_from_hex("#5B6B80")

# Para texto con markup de Kivy
HEX_AZUL_OSCURO = "0B1F3A"
HEX_TURQUESA = "0E9A92"  # un poco más oscuro que TURQUESA para leerse bien sobre blanco


def nombre_marca():
    """«Smart» en azul y «Cost» en turquesa (requiere markup=True)."""
    return f"[color={HEX_AZUL_OSCURO}]Smart[/color][color={HEX_TURQUESA}]Cost[/color]"
