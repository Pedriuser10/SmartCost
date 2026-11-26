"""Reglas de inventario y costos, sin base de datos (funciones puras con Decimal).

Replican exactamente lo que hacen los triggers de PostgreSQL
(supabase/migrations/20261126000000_esquema_inicial.sql), para que el teléfono calcule
sin conexión los mismos valores que el servidor. Los resultados locales son
**provisionales**: al sincronizar manda lo que calcule el servidor (aprobado 2026-11-26).

- Cantidades en la unidad base del insumo (g, ml, unidad); dinero y cantidades con 6
  decimales, redondeo "mitad hacia afuera" (igual que round() de numeric en Postgres).
- Costo promedio ponderado: (stock × promedio + costo_total) / (stock + cantidad).
  Si el stock previo es 0 o negativo, o no hay promedio, pasa a ser el costo unitario.
- El costo de reposición se reemplaza solo si el nuevo dato no es más antiguo.
- Un consumo mayor al stock se permite y deja el aviso stock_negativo.
- Merma como fracción, igual que en la app: 0,1 = 10 %.
- Venta directa (2026-11-27): margen objetivo en porcentaje (30 = 30 %) sobre el precio;
  costos netos y precio de góndola con IVA, sugerido redondeado hacia arriba a $10.
  El precio de góndola nunca cambia solo: se aprueba.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from services.calculo_costos import a_unidad_base

_SEIS = Decimal("0.000001")
MARGEN_FUTURO = timedelta(days=1)   # tolerancia de reloj, igual que en el servidor


class ErrorInventario(ValueError):
    """Operación de inventario inválida (mismas reglas que rechaza el servidor)."""


def redondear(valor):
    return valor.quantize(_SEIS, rounding=ROUND_HALF_UP)


def decimal(valor):
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


@dataclass(frozen=True)
class EstadoInventario:
    stock_actual: Decimal = Decimal("0")
    costo_promedio: Decimal = None
    costo_reposicion: Decimal = None
    costo_actualizado_en: datetime = None


def _validar_fecha(fecha, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    if fecha.tzinfo is None:
        raise ErrorInventario("La fecha debe incluir zona horaria")
    if fecha > ahora + MARGEN_FUTURO:
        raise ErrorInventario("La fecha está en el futuro")


def costo_unitario(cantidad, costo_total):
    return redondear(decimal(costo_total) / decimal(cantidad))


def aplicar_compra(estado, cantidad, costo_total, comprada_en, ahora=None):
    cantidad, costo_total = decimal(cantidad), decimal(costo_total)
    if cantidad <= 0:
        raise ErrorInventario("La cantidad comprada debe ser mayor que cero")
    if costo_total < 0:
        raise ErrorInventario("El costo total no puede ser negativo")
    _validar_fecha(comprada_en, ahora)
    unitario = costo_unitario(cantidad, costo_total)
    if estado.stock_actual <= 0 or estado.costo_promedio is None:
        promedio = unitario
    else:
        promedio = redondear((estado.stock_actual * estado.costo_promedio + costo_total)
                             / (estado.stock_actual + cantidad))
    vigente = estado.costo_actualizado_en is None or comprada_en >= estado.costo_actualizado_en
    return EstadoInventario(
        stock_actual=estado.stock_actual + cantidad,
        costo_promedio=promedio,
        costo_reposicion=unitario if vigente else estado.costo_reposicion,
        costo_actualizado_en=max(comprada_en, estado.costo_actualizado_en or comprada_en),
    ), unitario


@dataclass(frozen=True)
class ResultadoConsumo:
    estado: EstadoInventario
    costo_unitario: Decimal      # costo promedio al momento; None si aún no hay compras
    costo_total: Decimal
    stock_negativo: bool


def aplicar_consumo(estado, cantidad, consumido_en=None, ahora=None):
    cantidad = decimal(cantidad)
    if cantidad <= 0:
        raise ErrorInventario("La cantidad consumida debe ser mayor que cero")
    if consumido_en is not None:
        _validar_fecha(consumido_en, ahora)
    unitario = estado.costo_promedio
    total = redondear(cantidad * unitario) if unitario is not None else None
    nuevo = replace(estado, stock_actual=estado.stock_actual - cantidad)
    return ResultadoConsumo(nuevo, unitario, total, nuevo.stock_actual < 0)


def aplicar_costo_mercado(estado, costo_unitario_nuevo, vigente_desde, ahora=None):
    costo = decimal(costo_unitario_nuevo)
    if costo < 0:
        raise ErrorInventario("El costo debe ser cero o positivo")
    _validar_fecha(vigente_desde, ahora)
    if estado.costo_actualizado_en is not None and vigente_desde < estado.costo_actualizado_en:
        return estado                    # dato más antiguo que el vigente: no lo reemplaza
    return replace(estado, costo_reposicion=redondear(costo), costo_actualizado_en=vigente_desde)


def cantidad_para_produccion(cantidad, unidad, unidad_base, porciones, merma_pct):
    """cantidad × factor de la unidad × porciones × (1 + merma). None si no convierte (D4)."""
    en_base = a_unidad_base(cantidad, unidad, unidad_base)
    if en_base is None:
        return None
    return redondear(en_base * decimal(porciones) * (1 + decimal(merma_pct or 0)))


# ---------- venta directa y precio de venta ----------

REDONDEO_PRECIO = Decimal("10")
_CENTESIMOS = Decimal("0.01")


def precio_sugerido(costo, margen_pct, tasa_iva, redondeo=REDONDEO_PRECIO):
    """Precio con IVA = costo neto × (1 + IVA) / (1 − margen/100), hacia arriba a $10. None si falta un dato.

    Igual que privado.precio_sugerido() en PostgreSQL: el IVA se multiplica antes de dividir y se
    redondea a 6 decimales antes de subir, para que una división periódica no convierta $850 en $860.
    """
    if costo is None or margen_pct is None or tasa_iva is None:
        return None
    margen = decimal(margen_pct)
    if not Decimal("0") <= margen < Decimal("100"):
        raise ErrorInventario("El margen objetivo va de 0 a menos de 100 %")
    bruto = redondear(decimal(costo) * (1 + decimal(tasa_iva)) / (1 - margen / 100))
    return (bruto / redondeo).to_integral_value(rounding=ROUND_CEILING) * redondeo


def margen_real(precio_con_iva, costo, tasa_iva):
    """Margen (%) que deja un precio con IVA frente al costo neto. None si no se puede calcular."""
    if precio_con_iva is None or costo is None or decimal(precio_con_iva) <= 0:
        return None
    neto = decimal(precio_con_iva) / (1 + decimal(tasa_iva))
    return ((neto - decimal(costo)) / neto * 100).quantize(_CENTESIMOS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ResultadoVenta:
    estado: EstadoInventario
    precio_unitario: Decimal
    total: Decimal            # cobrado, con IVA
    ingreso_neto: Decimal     # total sin IVA
    costo_unitario: Decimal   # costo promedio al vender; None si aún no hay compras
    costo_venta: Decimal
    utilidad: Decimal
    stock_negativo: bool


def aplicar_venta(estado, cantidad, precio_unitario, tasa_iva, vendido_en=None, ahora=None):
    """Descuenta stock y costea la venta al costo promedio (como privado.aplicar_venta)."""
    cantidad = decimal(cantidad)
    if cantidad <= 0:
        raise ErrorInventario("La cantidad vendida debe ser mayor que cero")
    if precio_unitario is None:
        raise ErrorInventario("El producto no tiene precio de venta aprobado")
    precio = decimal(precio_unitario).quantize(_CENTESIMOS, rounding=ROUND_HALF_UP)
    if precio < 0:
        raise ErrorInventario("El precio no puede ser negativo")
    if vendido_en is not None:
        _validar_fecha(vendido_en, ahora)
    total = (cantidad * precio).quantize(_CENTESIMOS, rounding=ROUND_HALF_UP)
    ingreso = redondear(total / (1 + decimal(tasa_iva)))
    costo_u = estado.costo_promedio
    costo = redondear(cantidad * costo_u) if costo_u is not None else None
    nuevo = replace(estado, stock_actual=estado.stock_actual - cantidad)
    return ResultadoVenta(nuevo, precio, total, ingreso, costo_u, costo,
                          ingreso - costo if costo is not None else None, nuevo.stock_actual < 0)
