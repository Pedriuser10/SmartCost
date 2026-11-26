"""Informe de D5: costo de cada plato con la fórmula actual frente al costo proyectado.

SOLO LECTURA: abre los datos sin modificarlos (el JSON se lee; SQLite se abre en modo ro).
El resultado contiene datos del negocio (nombres, precios): no lo guardes en Git.

Uso, desde la raíz del repositorio:
    python herramientas/informe_costos.py --json  <ruta a app.json>
    python herramientas/informe_costos.py --sqlite <ruta a smartcost.db>

- Fórmula actual: services.calculo_costos.costo_real_plato (no cambia, D5).
- Proyectado: costo_proyectado_plato, con el costo de reposición y la unidad base.
  Solo se calcula si TODOS los ingredientes tienen unidad confirmada y costo; si no, el
  plato queda "pendiente" con el motivo. Nada se adivina (D4/D6).
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.calculo_costos import comparar_formulas, costo_real_plato  # noqa: E402


def _desde_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    insumos = {i["id"]: i for i in datos.get("insumos", [])}
    for plato in datos.get("platos", []):
        usados, proyectados = [], []
        for ing in plato.get("ingredientes", []):
            insumo = insumos.get(ing["insumo_id"])
            if insumo is None:
                continue                      # igual que la app: un insumo borrado no cuenta
            usados.append({**insumo, "cantidad": ing["cantidad"]})
            # El JSON no tiene unidad base ni costo de reposición: queda pendiente
            proyectados.append({"nombre": insumo["nombre"], "cantidad": ing["cantidad"], "unidad": None,
                                "unidad_base": None, "costo_reposicion": None,
                                "merma_pct": insumo.get("merma_pct", 0)})
        yield plato, usados, proyectados


def _desde_sqlite(ruta):
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version < 2:
            raise SystemExit(f"La base tiene el esquema {version}; el informe necesita el 2 (inventario).")
        for plato in con.execute("SELECT * FROM platos WHERE deleted_at IS NULL ORDER BY nombre COLLATE NOCASE"):
            filas = con.execute(
                "SELECT i.*, r.cantidad AS cant, r.unidad AS unidad_receta FROM plato_insumos r"
                " JOIN insumos i ON i.id = r.insumo_id AND i.deleted_at IS NULL"
                " WHERE r.plato_id = ? AND r.deleted_at IS NULL ORDER BY r.id", (plato["id"],)).fetchall()
            usados = [{"nombre": f["nombre"], "cantidad": f["cant"], "precio": f["precio"],
                       "merma_pct": f["merma_pct"]} for f in filas]
            proyectados = [{
                "nombre": f["nombre"], "cantidad": f["cant"], "unidad": f["unidad_receta"],
                "unidad_base": f["unidad_base"], "merma_pct": f["merma_pct"],
                "costo_reposicion": None if f["costo_reposicion"] is None else Decimal(f["costo_reposicion"]),
                "costo_actualizado_en": None if f["costo_actualizado_en"] is None
                else datetime.fromisoformat(f["costo_actualizado_en"]),
                "stock_actual": f["stock_actual"],
            } for f in filas]
            yield dict(plato), usados, proyectados
    finally:
        con.close()


def filas_informe(origen, ahora=None):
    """Una fila por plato: actual, proyectado (o None) y avisos."""
    for plato, usados, proyectados in origen:
        mano_obra = plato.get("mano_obra", 0) or 0
        if not proyectados:
            yield {"plato": plato["nombre"], "actual": Decimal(str(costo_real_plato(usados, mano_obra))),
                   "proyectado": None, "diferencia": None, "pendientes": [], "avisos": ["sin ingredientes"]}
            continue
        c = comparar_formulas(usados, proyectados, mano_obra, ahora)
        d = c["detalle"]
        avisos = []
        if d.desactualizados:
            avisos.append("precio con más de 30 días: " + ", ".join(d.desactualizados))
        if d.stock_negativo:
            avisos.append("stock negativo: " + ", ".join(d.stock_negativo))
        yield {"plato": plato["nombre"], "actual": c["actual"],
               "proyectado": c["proyectado"] if c["completo"] else None,
               "diferencia": c["diferencia"] if c["completo"] else None,
               "pendientes": d.unidad_incompatible + d.sin_costo, "avisos": avisos}


def _pesos(valor):
    return "—" if valor is None else f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def imprimir(filas, salida=sys.stdout):
    filas = list(filas)
    salida.write("| Plato | Costo actual | Costo proyectado | Diferencia | Pendiente / avisos |\n")
    salida.write("|---|---:|---:|---:|---|\n")
    for f in filas:
        notas = []
        if f["pendientes"]:
            notas.append(f"{len(f['pendientes'])} ingrediente(s) sin unidad base o sin costo")
        notas += f["avisos"]
        salida.write(f"| {f['plato']} | {_pesos(f['actual'])} | {_pesos(f['proyectado'])} | "
                     f"{_pesos(f['diferencia'])} | {'; '.join(notas)} |\n")
    listos = sum(1 for f in filas if f["proyectado"] is not None)
    salida.write(f"\n{listos} de {len(filas)} platos con costo proyectado completo.\n")
    return filas


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--json", help="app.json de la app actual")
    g.add_argument("--sqlite", help="smartcost.db (esquema 2)")
    args = p.parse_args(argv)
    origen = _desde_json(args.json) if args.json else _desde_sqlite(args.sqlite)
    sys.stderr.write("Aviso: el informe contiene datos del negocio; no lo subas a Git.\n\n")
    imprimir(filas_informe(origen))


if __name__ == "__main__":
    main()
