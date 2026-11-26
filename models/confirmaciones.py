"""Confirmación de la unidad base de cada insumo (D4/D6), antes de migrar a la base nueva.

Hoy la unidad es texto libre ("10kg", "kg", "un", "12"…) y mezcla unidad de medida con
presentación de compra (8.9). Para que un insumo entre al inventario hay que confirmar,
caso por caso:

1. su unidad base (g, ml o unidad);
2. a qué cantidad corresponde el precio guardado (p. ej. $5.000 = un envase de 10 kg);
3. en qué unidad están las cantidades de sus recetas (p. ej. kg).

Reglas (D6):
- **No modifica app.json.** Las confirmaciones van en un archivo aparte,
  <user_data_dir>/datos/confirmaciones_unidades.json, con escritura atómica.
- La sugerencia a partir del texto solo rellena el formulario; nada se confirma solo.
- Cada confirmación guarda una huella SHA-256 del nombre y la unidad del insumo. Si alguno
  cambia, queda "por revisar" y no se usa. También se registra el SHA-256 del app.json
  completo en el momento de confirmar, como trazabilidad.
- Un cambio de precio o de merma no la invalida: la confirmación describe la presentación,
  no el precio. La migración vuelve a validar los costos con los valores de ese momento.
"""
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from models import rutas
from services.calculo_costos import UNIDADES

NOMBRE_ARCHIVO = "confirmaciones_unidades.json"
VERSION = 1
BASES = ("g", "ml", "unidad")

PENDIENTE, CONFIRMADO, REVISAR = "pendiente", "confirmado", "revisar"

# Formas en que aparecen las unidades en los datos y plantillas. Solo se sugieren las que
# no dejan dudas de dimensión; "cc", "porción", "taza" y similares quedan sin sugerencia
# porque su catálogo sigue pendiente (8.10).
_ALIAS = {
    "g": "g", "gr": "g", "grs": "g", "gramo": "g", "gramos": "g",
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg",
    "mg": "mg",
    "ml": "ml",
    "l": "l", "lt": "l", "lts": "l", "litro": "l", "litros": "l",
    "un": "unidad", "und": "unidad", "u": "unidad", "unidad": "unidad", "unidades": "unidad",
    "docena": "docena", "docenas": "docena",
}
_PATRON = re.compile(r"^\s*(\d+(?:[.,]\d+)?)?\s*([^\d\s.,]+)?\s*$")


class ErrorConfirmacion(ValueError):
    pass


def archivo():
    return os.path.join(rutas.datos_dir(), NOMBRE_ARCHIVO)


def huella(insumo):
    """SHA-256 de lo que define la interpretación de la unidad: id, nombre y unidad."""
    clave = json.dumps({"id": insumo["id"], "nombre": insumo["nombre"], "unidad": insumo["unidad"]},
                       ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()


def sha256_app():
    ruta = rutas.archivo_app()
    if not os.path.exists(ruta):
        return None
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


# ---------- sugerencia (solo rellena el formulario) ----------

@dataclass
class Sugerencia:
    unidad_base: str
    contenido: Decimal
    unidad_contenido: str
    unidad_receta: str


def sugerir(texto_unidad):
    """Interpretación probable del texto, o None si no es segura (p. ej. "12" o "porción")."""
    m = _PATRON.match(texto_unidad or "")
    if not m or not m.group(2):
        return None
    codigo = _ALIAS.get(m.group(2).lower())
    if codigo is None:
        return None
    numero = Decimal(m.group(1).replace(",", ".")) if m.group(1) else Decimal("1")
    if numero <= 0:
        return None
    base = UNIDADES[codigo][1]
    # Si el texto trae un envase ("10kg"), las recetas probablemente usan la unidad sin número
    return Sugerencia(base, numero, codigo, codigo)


# ---------- opciones para la pantalla (la unidad base sale de la unidad elegida) ----------

NOMBRES = {"g": "gramos (g)", "kg": "kilos (kg)", "mg": "miligramos (mg)", "ml": "mililitros (ml)",
           "l": "litros (l)", "unidad": "unidades", "docena": "docenas"}
SINGULAR_BASE = {"g": "gramo", "ml": "mililitro", "unidad": "unidad"}
# Unidades que se ofrecen para anotar las recetas, por unidad base (mg queda fuera por rara)
UNIDADES_RECETA = {"g": ("kg", "g"), "ml": ("l", "ml"), "unidad": ("unidad", "docena")}


def base_de(unidad):
    """Unidad base de una unidad del catálogo: kg → g, l → ml, docena → unidad."""
    if unidad not in UNIDADES:
        raise ErrorConfirmacion(f"Unidad desconocida ({unidad})")
    return UNIDADES[unidad][1]


def cantidad_texto(numero, unidad):
    n = f"{Decimal(str(numero)).normalize():f}".replace(".", ",")
    corto = {"unidad": "unidad" if n == "1" else "unidades", "docena": "docena" if n == "1" else "docenas"}
    return f"{n} {corto.get(unidad, unidad)}"


def numero_suelto(texto_unidad):
    """El número de una unidad sin palabra ("12"), o None."""
    m = _PATRON.match(texto_unidad or "")
    if not m or m.group(2) or not m.group(1):
        return None
    n = Decimal(m.group(1).replace(",", "."))
    return n if n > 0 else None


def opciones_compra(insumo):
    """Opciones para "¿Qué compras por $X?": (contenido, unidad, detalle). La primera es la sugerida.

    Con sugerencia ("10kg"): 10 kg (sugerido) y, si no es 1, también 1 kg.
    Con un número suelto ("12"): 12 unidades, 12 kg y 12 l como atajos, sin marcar ninguno.
    Sin nada interpretable: ninguna; queda solo "Otra cantidad".
    """
    sug = sugerir(insumo["unidad"])
    if sug:
        opciones = [(sug.contenido, sug.unidad_contenido, f"Sugerido por «{insumo['unidad']}»")]
        if sug.contenido != 1:
            opciones.append((Decimal("1"), sug.unidad_contenido, ""))
        return opciones, True
    n = numero_suelto(insumo["unidad"])
    if n is not None:
        return [(n, "unidad", ""), (n, "kg", ""), (n, "l", "")], False
    return [], False


# ---------- interpretación e impacto (D6.3) ----------

def _dec(valor, campo):
    try:
        d = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ErrorConfirmacion(f"{campo}: no es un número") from None
    if not d.is_finite():
        raise ErrorConfirmacion(f"{campo}: no es un número")
    return d


def _misma_dimension(unidad, unidad_base, campo):
    if unidad not in UNIDADES:
        raise ErrorConfirmacion(f"{campo}: unidad desconocida ({unidad})")
    if UNIDADES[unidad][1] != unidad_base:
        raise ErrorConfirmacion(f"{campo}: {unidad} no se puede convertir a {unidad_base} (D4)")
    return UNIDADES[unidad][2]


def interpretar(insumo, unidad_base, contenido, unidad_contenido, unidad_receta):
    """Valida la interpretación y devuelve el costo por unidad base. Lanza ErrorConfirmacion."""
    if unidad_base not in BASES:
        raise ErrorConfirmacion("La unidad base debe ser g, ml o unidad")
    contenido = _dec(contenido, "Cantidad que cubre el precio")
    if contenido <= 0:
        raise ErrorConfirmacion("La cantidad que cubre el precio debe ser mayor que cero")
    factor_contenido = _misma_dimension(unidad_contenido, unidad_base, "Unidad del precio")
    _misma_dimension(unidad_receta, unidad_base, "Unidad de las recetas")
    precio = _dec(insumo["precio"], "Precio")
    return precio / (contenido * factor_contenido)


@dataclass
class Impacto:
    plato: str
    cantidad: Decimal
    costo_hoy: Decimal          # cantidad × precio × (1 + merma), como la fórmula actual
    costo_interpretado: Decimal  # cantidad × factor × costo por unidad base × (1 + merma)


def impacto(insumo, usos, unidad_base, contenido, unidad_contenido, unidad_receta):
    """Costo de este ingrediente en cada plato que lo usa, hoy y con la interpretación.

    usos: lista de (nombre del plato, cantidad en la receta).
    """
    costo_base = interpretar(insumo, unidad_base, contenido, unidad_contenido, unidad_receta)
    factor_receta = UNIDADES[unidad_receta][2]
    merma = Decimal("1") + _dec(insumo.get("merma_pct") or 0, "Merma")
    precio = _dec(insumo["precio"], "Precio")
    resultado = []
    for plato, cantidad in usos:
        c = _dec(cantidad, "Cantidad")
        resultado.append(Impacto(plato, c, (c * precio * merma).quantize(Decimal("0.01")),
                                 (c * factor_receta * costo_base * merma).quantize(Decimal("0.01"))))
    return costo_base, resultado


# ---------- archivo de confirmaciones ----------

def cargar():
    ruta = archivo()
    if not os.path.exists(ruta):
        return {"version": VERSION, "confirmaciones": {}}
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    if datos.get("version") != VERSION or not isinstance(datos.get("confirmaciones"), dict):
        raise ErrorConfirmacion("El archivo de confirmaciones tiene un formato desconocido: no se modifica.")
    return datos


def _guardar(datos):
    os.makedirs(rutas.datos_dir(), exist_ok=True)
    rutas.escribir_json_atomico(archivo(), datos)


def estado(insumo, datos=None):
    datos = datos if datos is not None else cargar()
    c = datos["confirmaciones"].get(str(insumo["id"]))
    if c is None:
        return PENDIENTE
    return CONFIRMADO if c.get("huella") == huella(insumo) else REVISAR


def confirmacion(insumo, datos=None):
    """La confirmación vigente del insumo, o None si no hay o quedó por revisar."""
    datos = datos if datos is not None else cargar()
    c = datos["confirmaciones"].get(str(insumo["id"]))
    return c if c is not None and c.get("huella") == huella(insumo) else None


def confirmar(insumo, unidad_base, contenido, unidad_contenido, unidad_receta):
    """Guarda la decisión explícita del usuario para este insumo."""
    costo_base = interpretar(insumo, unidad_base, contenido, unidad_contenido, unidad_receta)
    datos = cargar()
    datos["confirmaciones"][str(insumo["id"])] = {
        "nombre": insumo["nombre"],
        "unidad_original": insumo["unidad"],
        "precio_al_confirmar": str(insumo["precio"]),
        "unidad_base": unidad_base,
        "contenido": str(_dec(contenido, "Cantidad")),
        "unidad_contenido": unidad_contenido,
        "unidad_receta": unidad_receta,
        "costo_por_unidad_base": str(costo_base),
        "huella": huella(insumo),
        "sha256_app_json": sha256_app(),
        "confirmado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _guardar(datos)
    return costo_base


def quitar(insumo_id):
    datos = cargar()
    if datos["confirmaciones"].pop(str(insumo_id), None) is not None:
        _guardar(datos)


def resumen(insumos):
    """Cuántos insumos hay en cada estado (para el botón de Mis Recetas)."""
    datos = cargar()
    conteo = {PENDIENTE: 0, CONFIRMADO: 0, REVISAR: 0}
    for i in insumos:
        conteo[estado(i, datos)] += 1
    return conteo
