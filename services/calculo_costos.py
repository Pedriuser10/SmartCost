"""Lógica de negocio pura: costo real, margen y clasificación de rentabilidad."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP


def costo_real_plato(insumos_usados, costo_mano_obra=0):
    total = 0.0
    for item in insumos_usados:
        total += item["cantidad"] * item["precio"] * (1 + item.get("merma_pct", 0))
    return round(total + costo_mano_obra, 2)


def margen(precio_venta, costo_real):
    if precio_venta <= 0:
        return 0.0
    return round(((precio_venta - costo_real) / precio_venta) * 100, 2)


def clasificar_margen(margen_pct):
    if margen_pct > 30:
        return "bueno"
    elif margen_pct >= 10:
        return "regular"
    else:
        return "malo"


COLOR_MARGEN = {
    "bueno": (0.29, 0.68, 0.31, 1),
    "regular": (0.95, 0.73, 0.13, 1),
    "malo": (0.83, 0.24, 0.24, 1),
}

# =============================================================================
# Costo proyectado (cotizaciones y recetas) con el costo de reposición
#
# Aprobado el 2026-11-26. Convive con costo_real_plato(), que NO cambia (D5): las
# pantallas siguen usando la fórmula actual hasta aprobar la comparación entre ambas.
# Diferencias con la fórmula actual:
#   - usa el costo de reposición por unidad base (último costo de compra o de mercado),
#     no el campo "precio" de hoy;
#   - convierte la cantidad del ingrediente a la unidad base del insumo, solo dentro
#     de la misma dimensión (D4: nunca masa a volumen);
#   - la merma se guarda como fracción, igual que hoy (0,1 = 10 % → factor 1,10);
#   - calcula con Decimal, sin errores de redondeo de float.
# =============================================================================

# Mismo catálogo que public.unidades en supabase/migrations (una prueba verifica que coincidan)
UNIDADES = {
    #  código: (dimensión, unidad base, factor a la base)
    "g":      ("masa",    "g",      Decimal("1")),
    "ml":     ("volumen", "ml",     Decimal("1")),
    "unidad": ("conteo",  "unidad", Decimal("1")),
    "kg":     ("masa",    "g",      Decimal("1000")),
    "mg":     ("masa",    "g",      Decimal("0.001")),
    "l":      ("volumen", "ml",     Decimal("1000")),
    "docena": ("conteo",  "unidad", Decimal("12")),
}

DIAS_COSTO_VIGENTE = 30
_CENTAVOS = Decimal("0.01")


def _decimal(valor):
    # str() evita arrastrar el error binario de un float (0.1 → 0.1000000000000000055…)
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def a_unidad_base(cantidad, unidad, unidad_base):
    """Convierte una cantidad a la unidad base del insumo. None si no se puede (D4)."""
    if unidad not in UNIDADES or unidad_base not in UNIDADES:
        return None
    _dimension, base, factor = UNIDADES[unidad]
    if UNIDADES[unidad_base][1] != unidad_base or base != unidad_base:
        return None                     # otra dimensión, o unidad_base no es una unidad base
    return _decimal(cantidad) * factor


def costo_desactualizado(costo_actualizado_en, ahora=None, dias=DIAS_COSTO_VIGENTE):
    """True si el costo de reposición tiene más de `dias` días (alerta de desfase)."""
    if costo_actualizado_en is None:
        return False                    # sin costo: se informa aparte, en sin_costo
    ahora = ahora or datetime.now(timezone.utc)
    return ahora - costo_actualizado_en > timedelta(days=dias)


@dataclass
class CostoProyectado:
    costo: Decimal                                   # suma de lo que sí se pudo calcular + mano de obra
    completo: bool                                   # False si faltó algún ingrediente
    sin_costo: list = field(default_factory=list)            # ingredientes sin costo de reposición
    unidad_incompatible: list = field(default_factory=list)  # sin unidad o de otra dimensión
    desactualizados: list = field(default_factory=list)      # costo con más de 30 días
    stock_negativo: list = field(default_factory=list)       # aviso de inventario


def costo_proyectado_plato(ingredientes, costo_mano_obra=0, ahora=None):
    """Costo de un plato para cotizar, con el costo de reposición de cada insumo.

    Cada ingrediente es un dict con: nombre, cantidad, unidad (de la receta),
    unidad_base, costo_reposicion (por unidad base), merma_pct (fracción: 0,1 = 10 %) y,
    opcionales, costo_actualizado_en (datetime con zona) y stock_actual.
    Un ingrediente que no se puede calcular no se inventa: queda en la lista
    correspondiente y el resultado se marca como incompleto.
    """
    total = Decimal("0")
    r = CostoProyectado(costo=Decimal("0"), completo=True)
    for ing in ingredientes:
        nombre = ing.get("nombre", "?")
        cantidad_base = a_unidad_base(ing["cantidad"], ing.get("unidad"), ing.get("unidad_base"))
        if cantidad_base is None:
            r.unidad_incompatible.append(nombre)
            continue
        if ing.get("costo_reposicion") is None:
            r.sin_costo.append(nombre)
            continue
        merma = Decimal("1") + _decimal(ing.get("merma_pct") or 0)
        total += cantidad_base * _decimal(ing["costo_reposicion"]) * merma
        if costo_desactualizado(ing.get("costo_actualizado_en"), ahora):
            r.desactualizados.append(nombre)
        if ing.get("stock_actual") is not None and _decimal(ing["stock_actual"]) < 0:
            r.stock_negativo.append(nombre)
    r.completo = not (r.sin_costo or r.unidad_incompatible)
    r.costo = (total + _decimal(costo_mano_obra)).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)
    return r


def comparar_formulas(insumos_usados, ingredientes_proyectados, costo_mano_obra=0, ahora=None):
    """Para el informe de D5: costo con la fórmula actual frente al costo proyectado."""
    actual = Decimal(str(costo_real_plato(insumos_usados, costo_mano_obra)))
    nuevo = costo_proyectado_plato(ingredientes_proyectados, costo_mano_obra, ahora)
    return {"actual": actual, "proyectado": nuevo.costo, "diferencia": nuevo.costo - actual,
            "completo": nuevo.completo, "detalle": nuevo}
