import json
import os
from datetime import datetime

from models import rutas


def imagenes_dir():
    """Carpeta donde se guardan las fotos de los platos (dentro de los datos persistentes)."""
    return rutas.imagenes_dir()


def ruta_imagen(valor):
    """Devuelve la ruta absoluta de la foto de un plato, o None si no existe.

    En el JSON basta guardar el nombre del archivo (ej. "Ceviche.png"); la
    carpeta se resuelve siempre desde aquí, así funciona sin importar desde
    qué carpeta ejecutes `python main.py`. Acepta también rutas viejas como
    "SmartCost/data/imagenes/Ceviche.png" (usa solo el nombre del archivo).
    Busca primero en las fotos del usuario y luego en las de ejemplo de la app.
    """
    if not valor:
        return None
    nombre = os.path.basename(valor.replace("\\", "/"))
    for carpeta in (imagenes_dir(), rutas.ORIGEN_IMAGENES_DIR):
        ruta = os.path.join(carpeta, nombre)
        if os.path.exists(ruta):
            return ruta
    return None


class Insumo:
    def __init__(self, id_insumo, nombre, unidad, precio, merma_pct, fecha_creacion=None):
        self.id = id_insumo
        self.nombre = nombre
        self.unidad = unidad
        self.precio = precio
        self.merma_pct = merma_pct
        self.fecha_creacion = fecha_creacion or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "unidad": self.unidad,
            "precio": self.precio,
            "merma_pct": self.merma_pct,
            "fecha_creacion": self.fecha_creacion,
        }


class Plato:
    def __init__(self, id_plato, nombre, precio_venta, mano_obra, imagen=None, ingredientes=None, fecha_creacion=None):
        self.id = id_plato
        self.nombre = nombre
        self.precio_venta = precio_venta
        self.mano_obra = mano_obra
        self.imagen = imagen
        self.ingredientes = ingredientes if ingredientes is not None else []
        self.fecha_creacion = fecha_creacion or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "precio_venta": self.precio_venta,
            "mano_obra": self.mano_obra,
            "imagen": self.imagen,
            "ingredientes": self.ingredientes,
            "fecha_creacion": self.fecha_creacion,
        }


# ---------- HELPERS JSON ----------

def _cargar_datos():
    archivo = rutas.archivo_app()
    if not os.path.exists(archivo):
        return {"insumos": [], "platos": [], "next_insumo_id": 1, "next_plato_id": 1, "next_rel_id": 1}
    with open(archivo, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar_datos(datos):
    archivo = rutas.archivo_app()
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    rutas.escribir_json_atomico(archivo, datos)


# ---------- INSUMOS ----------

def get_insumos():
    datos = _cargar_datos()
    return sorted(datos["insumos"], key=lambda x: x["nombre"].lower())


def add_insumo(nombre, unidad, precio, merma_pct):
    datos = _cargar_datos()
    nuevo_insumo = Insumo(datos["next_insumo_id"], nombre, unidad, precio, merma_pct)
    datos["insumos"].append(nuevo_insumo.to_dict())
    datos["next_insumo_id"] += 1
    _guardar_datos(datos)


def update_insumo(insumo_id, nombre, unidad, precio, merma_pct):
    datos = _cargar_datos()
    for insumo in datos["insumos"]:
        if insumo["id"] == insumo_id:
            insumo["nombre"] = nombre
            insumo["unidad"] = unidad
            insumo["precio"] = precio
            insumo["merma_pct"] = merma_pct
            break
    _guardar_datos(datos)


def delete_insumo(insumo_id):
    datos = _cargar_datos()
    datos["insumos"] = [i for i in datos["insumos"] if i["id"] != insumo_id]
    # Eliminar en cascada el insumo de las recetas de los platos
    for plato in datos["platos"]:
        plato["ingredientes"] = [ing for ing in plato["ingredientes"] if ing["insumo_id"] != insumo_id]
    _guardar_datos(datos)


# ---------- PLATOS ----------

def get_platos():
    datos = _cargar_datos()
    return sorted(datos["platos"], key=lambda x: x["nombre"].lower())


def get_plato(plato_id):
    datos = _cargar_datos()
    for plato in datos["platos"]:
        if plato["id"] == plato_id:
            return plato
    return None


def get_insumos_de_plato(plato_id):
    datos = _cargar_datos()
    plato = get_plato(plato_id)
    if not plato:
        return []

    resultado = []
    for ing in plato["ingredientes"]:
        for insumo in datos["insumos"]:
            if insumo["id"] == ing["insumo_id"]:
                item = insumo.copy()
                item["rel_id"] = ing["rel_id"]
                item["cantidad"] = ing["cantidad"]
                resultado.append(item)
                break
    return resultado


def add_plato(nombre, precio_venta, mano_obra, imagen=None):
    datos = _cargar_datos()
    nuevo_plato = Plato(datos["next_plato_id"], nombre, precio_venta, mano_obra, imagen)
    datos["platos"].append(nuevo_plato.to_dict())
    plato_id = datos["next_plato_id"]
    datos["next_plato_id"] += 1
    _guardar_datos(datos)
    return plato_id


def update_plato(plato_id, nombre, precio_venta, mano_obra, imagen=None):
    datos = _cargar_datos()
    for plato in datos["platos"]:
        if plato["id"] == plato_id:
            plato["nombre"] = nombre
            plato["precio_venta"] = precio_venta
            plato["mano_obra"] = mano_obra
            if imagen is not None:
                plato["imagen"] = imagen
            break
    _guardar_datos(datos)


def delete_plato(plato_id):
    datos = _cargar_datos()
    datos["platos"] = [p for p in datos["platos"] if p["id"] != plato_id]
    _guardar_datos(datos)


def add_insumo_a_plato(plato_id, insumo_id, cantidad):
    datos = _cargar_datos()
    for plato in datos["platos"]:
        if plato["id"] == plato_id:
            plato["ingredientes"].append({
                "rel_id": datos["next_rel_id"],
                "insumo_id": insumo_id,
                "cantidad": cantidad,
            })
            datos["next_rel_id"] += 1
            break
    _guardar_datos(datos)


def quitar_insumo_de_plato(rel_id):
    datos = _cargar_datos()
    for plato in datos["platos"]:
        plato["ingredientes"] = [ing for ing in plato["ingredientes"] if ing["rel_id"] != rel_id]
    _guardar_datos(datos)