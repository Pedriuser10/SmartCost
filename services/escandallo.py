"""Escandallo de un plato: costo por ingrediente, total, utilidad y margen.

Reglas (decisiones del 2026-11-27):
- Fórmula de merma "actual" = precio × (1 + merma), la de costo_real_plato() (D5). La
  "propuesta" = precio ÷ (1 − merma) se calcula al lado, sin reemplazar a la actual.
- Un insumo con la unidad CONFIRMADA (models/confirmaciones) se costea por unidad base:
  cantidad × factor de la unidad de receta × precio ÷ (contenido × factor del contenido).
- Sin confirmar se costea como hoy (cantidad × precio) y, si su unidad parece un paquete
  ("8kg") o no se entiende ("12"), se marca con un aviso y lo que costaría al confirmarlo.
  Nunca se reinterpreta solo (D4/D6).
"""
from dataclasses import dataclass, field
from decimal import Decimal

from models import confirmaciones, storage
from services.calculo_costos import UNIDADES

FORMULAS = ("actual", "propuesta")


def _d(valor):
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def factor_merma(merma, formula="actual"):
    m = _d(merma or 0)
    if formula == "actual":
        return 1 + m
    if m >= 1:
        raise ValueError("La merma debe ser menor que 100 %")
    return 1 / (1 - m)


@dataclass
class Fila:
    rel_id: int
    nombre: str
    cantidad: Decimal
    unidad: str
    precio: Decimal
    unidad_original: str
    merma: Decimal
    subtotal: Decimal
    confirmado: bool
    aviso: str = ""
    si_confirma: Decimal = None


@dataclass
class Escandallo:
    filas: list
    porciones: Decimal
    insumos: Decimal
    mano_obra: Decimal
    costo: Decimal
    precio: Decimal
    utilidad: Decimal
    margen: Decimal
    costo_otra_formula: Decimal
    margen_otra_formula: Decimal
    avisos: int = field(default=0)


def _costo(insumo, cantidad, formula, conf):
    precio = _d(insumo["precio"])
    f = factor_merma(insumo.get("merma_pct"), formula)
    if conf:
        contenido = _d(conf["contenido"]) * UNIDADES[conf["unidad_contenido"]][2]
        return cantidad * UNIDADES[conf["unidad_receta"]][2] * precio / contenido * f
    return cantidad * precio * f


def calcular(plato, porciones=1, formula="actual", cantidades=None, mano_obra=None, precio=None):
    """Escandallo de `plato` (dict de storage). `cantidades` {rel_id: cantidad} simula cambios."""
    if formula not in FORMULAS:
        raise ValueError(f"Fórmula desconocida: {formula}")
    cantidades = cantidades or {}
    n = _d(porciones)
    try:
        datos = confirmaciones.cargar()
    except confirmaciones.ErrorConfirmacion:
        datos = {"confirmaciones": {}}
    otra = "propuesta" if formula == "actual" else "actual"
    filas, insumos, insumos_otra, avisos = [], Decimal(0), Decimal(0), 0
    for item in storage.get_insumos_de_plato(plato["id"]):
        cantidad = _d(cantidades.get(item["rel_id"], item["cantidad"]))
        conf = confirmaciones.confirmacion(item, datos)
        subtotal = _costo(item, cantidad, formula, conf) * n
        insumos += subtotal
        insumos_otra += _costo(item, cantidad, otra, conf) * n
        aviso, si_confirma = "", None
        if conf:
            unidad = conf["unidad_receta"]
        else:
            sug = confirmaciones.sugerir(item["unidad"])
            unidad = sug.unidad_receta if sug else ""
            if sug is None:
                aviso = f"Sin confirmar: «{item['unidad']}» no indica la cantidad"
            elif sug.contenido != 1:
                si_confirma = subtotal / sug.contenido
                aviso = (f"Sin confirmar: suma el paquete de "
                         f"{confirmaciones.cantidad_texto(sug.contenido, sug.unidad_contenido)}")
            if aviso:
                avisos += 1
        filas.append(Fila(item["rel_id"], item["nombre"], cantidad, unidad, _d(item["precio"]), item["unidad"],
                          _d(item.get("merma_pct") or 0), subtotal, bool(conf), aviso, si_confirma))
    mano = _d(plato["mano_obra"] if mano_obra is None else mano_obra) * n
    venta = _d(plato["precio_venta"] if precio is None else precio) * n
    costo, costo_otra = insumos + mano, insumos_otra + mano

    def margen(c):
        return (venta - c) / venta * 100 if venta > 0 else Decimal(0)

    return Escandallo(filas, n, insumos, mano, costo, venta, venta - costo, margen(costo),
                      costo_otra, margen(costo_otra), avisos)
