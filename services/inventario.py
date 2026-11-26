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
- Merma en porcentaje: 10 = 10 %.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

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
    """cantidad × factor de la unidad × porciones × (1 + merma/100). None si no convierte (D4)."""
    en_base = a_unidad_base(cantidad, unidad, unidad_base)
    if en_base is None:
        return None
    return redondear(en_base * decimal(porciones) * (1 + decimal(merma_pct or 0) / 100))
