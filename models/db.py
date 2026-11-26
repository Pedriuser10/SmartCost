"""Base de datos local SQLite (fase 1 de D7): esquema, operaciones y cola de sincronización.

Estado: módulo independiente, **todavía no conectado a la app**. La app sigue usando
models/storage.py (JSON). Este módulo ofrece la misma interfaz que storage.py para que el
cambio de motor sea un paso posterior y verificable.

Qué cumple de lo aprobado (CONTEXTO_PROYECTO.md, sección 8):
- D7: SQLite como base local; los cambios sobreviven al cierre de la app y al reinicio
  (transacciones con synchronous=FULL).
- D7: cola persistente de sincronización. Cada cambio y su operación en la cola se
  escriben en **la misma transacción**: o quedan los dos o ninguno.
  Cada operación tiene un UUID propio (idempotencia), estado, intentos y último error.
  Se guarda en el orden en que ocurrió, así un ingrediente nunca va antes que su plato.
  Si la app se cierra a mitad de una sincronización, las operaciones "en_proceso" vuelven
  a "pendiente" al abrir.
- D2 / 8.8: cada registro tiene un UUID global además del id entero local, que se mantiene
  para no cambiar las pantallas actuales.
- D1: las eliminaciones son lógicas (deleted_at) y no borran filas.
- D4 / D5: la unidad se guarda tal como la escribió el usuario. No se reinterpreta.
- D5: no cambia la fórmula de costos; los números se guardan igual que hoy en el JSON.
- Esquema 2, inventario (aprobado 2026-11-26): compras, consumos, producción y precio
  de mercado con las mismas reglas que PostgreSQL (services/inventario.py). Los valores
  son provisionales hasta que el servidor confirme los movimientos.

Fuera de esta fase, a propósito:
- Migrar los JSON actuales (D3 y D6 exigen informe y confirmación caso por caso).
- Supabase, negocios, roles y resolución de conflictos.
- Recibir del servidor el inventario confirmado (parte del cliente de sincronización).
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from services import inventario as inv
from services.calculo_costos import UNIDADES, costo_desactualizado, costo_proyectado_plato

NOMBRE_ARCHIVO = "smartcost.db"

ESTADOS_COLA = ("pendiente", "en_proceso", "sincronizada", "error", "conflicto")

# Cada entrada lleva el esquema de la versión N-1 a la N. Nunca se edita una versión ya
# publicada: los cambios futuros se agregan como una entrada nueva al final.
_MIGRACIONES = [
    """
    CREATE TABLE insumos (
        id              INTEGER PRIMARY KEY,
        uuid            TEXT    NOT NULL UNIQUE,
        nombre          TEXT    NOT NULL,
        unidad          TEXT    NOT NULL DEFAULT '',
        precio          REAL    NOT NULL DEFAULT 0,
        merma_pct       REAL    NOT NULL DEFAULT 0,
        fecha_creacion  TEXT    NOT NULL,
        version         INTEGER NOT NULL DEFAULT 1,
        updated_at      TEXT    NOT NULL,
        deleted_at      TEXT
    );
    CREATE TABLE platos (
        id              INTEGER PRIMARY KEY,
        uuid            TEXT    NOT NULL UNIQUE,
        nombre          TEXT    NOT NULL,
        precio_venta    REAL    NOT NULL DEFAULT 0,
        mano_obra       REAL    NOT NULL DEFAULT 0,
        imagen          TEXT,
        fecha_creacion  TEXT    NOT NULL,
        version         INTEGER NOT NULL DEFAULT 1,
        updated_at      TEXT    NOT NULL,
        deleted_at      TEXT
    );
    CREATE TABLE plato_insumos (
        id              INTEGER PRIMARY KEY,
        uuid            TEXT    NOT NULL UNIQUE,
        plato_id        INTEGER NOT NULL REFERENCES platos(id),
        insumo_id       INTEGER NOT NULL REFERENCES insumos(id),
        cantidad        REAL    NOT NULL,
        version         INTEGER NOT NULL DEFAULT 1,
        updated_at      TEXT    NOT NULL,
        deleted_at      TEXT
    );
    CREATE INDEX idx_plato_insumos_plato ON plato_insumos(plato_id);
    CREATE INDEX idx_plato_insumos_insumo ON plato_insumos(insumo_id);
    CREATE TABLE cola_sync (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        op_uuid         TEXT    NOT NULL UNIQUE,
        tabla           TEXT    NOT NULL,
        registro_uuid   TEXT    NOT NULL,
        operacion       TEXT    NOT NULL CHECK (operacion IN ('crear', 'actualizar', 'eliminar')),
        datos           TEXT    NOT NULL,
        estado          TEXT    NOT NULL DEFAULT 'pendiente'
                        CHECK (estado IN ('pendiente', 'en_proceso', 'sincronizada', 'error', 'conflicto')),
        intentos        INTEGER NOT NULL DEFAULT 0,
        ultimo_error    TEXT,
        creada_en       TEXT    NOT NULL,
        actualizada_en  TEXT    NOT NULL
    );
    CREATE INDEX idx_cola_estado ON cola_sync(estado, id);
    """,
    # 2: inventario (aprobado 2026-11-26). Decimales como TEXTO para no perder precisión;
    # se leen como Decimal. Las columnas antiguas (precio, merma_pct) no cambian.
    """
    ALTER TABLE insumos ADD COLUMN unidad_base TEXT;
    ALTER TABLE insumos ADD COLUMN stock_actual TEXT NOT NULL DEFAULT '0';
    ALTER TABLE insumos ADD COLUMN costo_promedio TEXT;
    ALTER TABLE insumos ADD COLUMN costo_reposicion TEXT;
    ALTER TABLE insumos ADD COLUMN costo_actualizado_en TEXT;
    ALTER TABLE plato_insumos ADD COLUMN unidad TEXT;
    CREATE TABLE compras_insumos (
        id                 INTEGER PRIMARY KEY,
        uuid               TEXT NOT NULL UNIQUE,
        insumo_id          INTEGER NOT NULL REFERENCES insumos(id),
        cantidad_comprada  TEXT NOT NULL,
        costo_total        TEXT NOT NULL,
        costo_unitario     TEXT NOT NULL,
        comprada_en        TEXT NOT NULL
    );
    CREATE TABLE producciones (
        id            INTEGER PRIMARY KEY,
        uuid          TEXT NOT NULL UNIQUE,
        plato_id      INTEGER NOT NULL REFERENCES platos(id),
        porciones     TEXT NOT NULL,
        costo_total   TEXT,
        producido_en  TEXT NOT NULL
    );
    CREATE TABLE consumos_insumos (
        id                INTEGER PRIMARY KEY,
        uuid              TEXT NOT NULL UNIQUE,
        insumo_id         INTEGER NOT NULL REFERENCES insumos(id),
        produccion_id     INTEGER REFERENCES producciones(id),
        cantidad          TEXT NOT NULL,
        costo_unitario    TEXT,
        costo_total       TEXT,
        stock_resultante  TEXT NOT NULL,
        stock_negativo    INTEGER NOT NULL,
        motivo            TEXT NOT NULL,
        consumido_en      TEXT NOT NULL
    );
    CREATE INDEX idx_compras_insumo ON compras_insumos(insumo_id);
    CREATE INDEX idx_consumos_insumo ON consumos_insumos(insumo_id);
    """,
]

# Columnas que calcula el servidor: no viajan en la cola (el cliente no puede escribirlas)
_SOLO_SERVIDOR = {"insumos": ("stock_actual", "costo_promedio", "costo_reposicion", "costo_actualizado_en")}
BASES = ("g", "ml", "unidad")
MOTIVOS_CONSUMO = ("consumo", "perdida", "ajuste")   # 'produccion' solo vía registrar_produccion

VERSION_ESQUEMA = len(_MIGRACIONES)


def _ahora_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _ahora_local():
    # Mismo formato que fecha_creacion en el JSON actual
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _texto(valor):
    return None if valor is None else str(valor)


def _dec(valor):
    return None if valor is None else Decimal(valor)


def _fecha(valor):
    return None if valor is None else datetime.fromisoformat(valor)


def _iso(fecha):
    return fecha.astimezone(timezone.utc).isoformat()


def _clave_nombre(fila):
    return fila["nombre"].lower()


class EsquemaMasNuevo(RuntimeError):
    """La base fue creada por una versión más nueva de la app: no se toca."""


class BaseLocal:
    def __init__(self, ruta):
        self.ruta = ruta
        self._con = sqlite3.connect(ruta, isolation_level=None)  # transacciones explícitas
        self._con.row_factory = sqlite3.Row
        try:
            self._con.execute("PRAGMA foreign_keys = ON")
            self._con.execute("PRAGMA journal_mode = WAL")
            self._con.execute("PRAGMA synchronous = FULL")
            self._migrar()
            self._recuperar_en_proceso()
        except BaseException:
            self._con.close()          # no dejar la conexión abierta si la base no se puede usar
            raise

    # ---------- infraestructura ----------

    def cerrar(self):
        self._con.close()

    def version_esquema(self):
        return self._con.execute("PRAGMA user_version").fetchone()[0]

    def _transaccion(self):
        return _Transaccion(self._con)

    def _migrar(self):
        actual = self.version_esquema()
        if actual > VERSION_ESQUEMA:
            raise EsquemaMasNuevo(
                f"La base tiene el esquema {actual} y esta versión de la app solo conoce hasta el {VERSION_ESQUEMA}."
            )
        for numero in range(actual, VERSION_ESQUEMA):
            with self._transaccion() as cur:
                for sentencia in _MIGRACIONES[numero].split(";"):
                    if sentencia.strip():
                        cur.execute(sentencia)
                cur.execute(f"PRAGMA user_version = {numero + 1}")

    def _recuperar_en_proceso(self):
        """Si la app se cerró durante una sincronización, esas operaciones se reintentan."""
        with self._transaccion() as cur:
            cur.execute(
                "UPDATE cola_sync SET estado = 'pendiente', actualizada_en = ? WHERE estado = 'en_proceso'",
                (_ahora_utc(),),
            )

    def _encolar(self, cur, tabla, registro_uuid, operacion, datos):
        ahora = _ahora_utc()
        cur.execute(
            "INSERT INTO cola_sync (op_uuid, tabla, registro_uuid, operacion, datos, creada_en, actualizada_en)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), tabla, registro_uuid, operacion,
             json.dumps(datos, ensure_ascii=False, sort_keys=True), ahora, ahora),
        )

    def _fila(self, cur, tabla, registro_id):
        return cur.execute(
            f"SELECT * FROM {tabla} WHERE id = ? AND deleted_at IS NULL", (registro_id,)
        ).fetchone()

    def _instantanea(self, cur, tabla, registro_id):
        """Datos que viajan en la cola: el registro con referencias por UUID, no por id local."""
        fila = dict(cur.execute(f"SELECT * FROM {tabla} WHERE id = ?", (registro_id,)).fetchone())
        fila.pop("id")
        for columna in _SOLO_SERVIDOR.get(tabla, ()):
            fila.pop(columna, None)
        if tabla == "plato_insumos":
            fila["plato_uuid"] = cur.execute("SELECT uuid FROM platos WHERE id = ?", (fila.pop("plato_id"),)).fetchone()[0]
            fila["insumo_uuid"] = cur.execute("SELECT uuid FROM insumos WHERE id = ?", (fila.pop("insumo_id"),)).fetchone()[0]
        return fila

    def _crear(self, cur, tabla, valores):
        valores = {"uuid": str(uuid.uuid4()), "updated_at": _ahora_utc(), **valores}
        columnas = ", ".join(valores)
        marcas = ", ".join("?" for _ in valores)
        cur.execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({marcas})", tuple(valores.values()))
        nuevo_id = cur.lastrowid
        self._encolar(cur, tabla, valores["uuid"], "crear", self._instantanea(cur, tabla, nuevo_id))
        return nuevo_id

    def _actualizar(self, cur, tabla, fila, cambios):
        asignaciones = ", ".join(f"{c} = ?" for c in cambios)
        cur.execute(
            f"UPDATE {tabla} SET {asignaciones}, version = version + 1, updated_at = ? WHERE id = ?",
            (*cambios.values(), _ahora_utc(), fila["id"]),
        )
        self._encolar(cur, tabla, fila["uuid"], "actualizar", self._instantanea(cur, tabla, fila["id"]))

    def _eliminar(self, cur, tabla, fila):
        cur.execute(
            f"UPDATE {tabla} SET deleted_at = ?, version = version + 1, updated_at = ? WHERE id = ?",
            (_ahora_utc(), _ahora_utc(), fila["id"]),
        )
        self._encolar(cur, tabla, fila["uuid"], "eliminar", self._instantanea(cur, tabla, fila["id"]))

    def _eliminar_relaciones(self, cur, columna, valor):
        for rel in cur.execute(
            f"SELECT * FROM plato_insumos WHERE {columna} = ? AND deleted_at IS NULL ORDER BY id", (valor,)
        ).fetchall():
            self._eliminar(cur, "plato_insumos", rel)

    # ---------- INSUMOS (misma interfaz que storage.py) ----------

    def _insumo_a_dict(self, fila):
        return {c: fila[c] for c in ("id", "nombre", "unidad", "precio", "merma_pct", "fecha_creacion")}

    def get_insumos(self):
        filas = self._con.execute("SELECT * FROM insumos WHERE deleted_at IS NULL ORDER BY id").fetchall()
        return sorted((self._insumo_a_dict(f) for f in filas), key=_clave_nombre)

    def add_insumo(self, nombre, unidad, precio, merma_pct):
        with self._transaccion() as cur:
            return self._crear(cur, "insumos", {
                "nombre": nombre, "unidad": unidad, "precio": precio, "merma_pct": merma_pct,
                "fecha_creacion": _ahora_local(),
            })

    def update_insumo(self, insumo_id, nombre, unidad, precio, merma_pct):
        with self._transaccion() as cur:
            fila = self._fila(cur, "insumos", insumo_id)
            if fila is not None:
                self._actualizar(cur, "insumos", fila,
                                 {"nombre": nombre, "unidad": unidad, "precio": precio, "merma_pct": merma_pct})

    def delete_insumo(self, insumo_id):
        """Borrado lógico. Igual que hoy, el insumo sale también de las recetas que lo usaban.

        Pendiente de decisión (8.10): cascada lógica o bloqueo si está en recetas.
        """
        with self._transaccion() as cur:
            fila = self._fila(cur, "insumos", insumo_id)
            if fila is not None:
                self._eliminar_relaciones(cur, "insumo_id", insumo_id)
                self._eliminar(cur, "insumos", fila)

    # ---------- PLATOS ----------

    def _ingredientes(self, plato_id):
        filas = self._con.execute(
            "SELECT id, insumo_id, cantidad FROM plato_insumos WHERE plato_id = ? AND deleted_at IS NULL ORDER BY id",
            (plato_id,),
        ).fetchall()
        return [{"rel_id": f["id"], "insumo_id": f["insumo_id"], "cantidad": f["cantidad"]} for f in filas]

    def _plato_a_dict(self, fila):
        d = {c: fila[c] for c in ("id", "nombre", "precio_venta", "mano_obra", "imagen")}
        d["ingredientes"] = self._ingredientes(fila["id"])
        d["fecha_creacion"] = fila["fecha_creacion"]
        return d

    def get_platos(self):
        filas = self._con.execute("SELECT * FROM platos WHERE deleted_at IS NULL ORDER BY id").fetchall()
        return sorted((self._plato_a_dict(f) for f in filas), key=_clave_nombre)

    def get_plato(self, plato_id):
        fila = self._con.execute("SELECT * FROM platos WHERE id = ? AND deleted_at IS NULL", (plato_id,)).fetchone()
        return self._plato_a_dict(fila) if fila else None

    def get_insumos_de_plato(self, plato_id):
        filas = self._con.execute(
            "SELECT i.*, r.id AS rel_id, r.cantidad FROM plato_insumos r"
            " JOIN insumos i ON i.id = r.insumo_id AND i.deleted_at IS NULL"
            " JOIN platos p ON p.id = r.plato_id AND p.deleted_at IS NULL"
            " WHERE r.plato_id = ? AND r.deleted_at IS NULL ORDER BY r.id",
            (plato_id,),
        ).fetchall()
        return [{**self._insumo_a_dict(f), "rel_id": f["rel_id"], "cantidad": f["cantidad"]} for f in filas]

    def add_plato(self, nombre, precio_venta, mano_obra, imagen=None):
        with self._transaccion() as cur:
            return self._crear(cur, "platos", {
                "nombre": nombre, "precio_venta": precio_venta, "mano_obra": mano_obra, "imagen": imagen,
                "fecha_creacion": _ahora_local(),
            })

    def update_plato(self, plato_id, nombre, precio_venta, mano_obra, imagen=None):
        with self._transaccion() as cur:
            fila = self._fila(cur, "platos", plato_id)
            if fila is not None:
                cambios = {"nombre": nombre, "precio_venta": precio_venta, "mano_obra": mano_obra}
                if imagen is not None:  # igual que storage.py: None conserva la foto actual
                    cambios["imagen"] = imagen
                self._actualizar(cur, "platos", fila, cambios)

    def delete_plato(self, plato_id):
        with self._transaccion() as cur:
            fila = self._fila(cur, "platos", plato_id)
            if fila is not None:
                self._eliminar_relaciones(cur, "plato_id", plato_id)
                self._eliminar(cur, "platos", fila)

    def add_insumo_a_plato(self, plato_id, insumo_id, cantidad, unidad=None):
        """Devuelve el rel_id nuevo, o None si el plato o el insumo no existen.

        unidad: código del catálogo (g, kg, ml…) o None = unidad antigua, sin convertir.
        """
        if unidad is not None and unidad not in UNIDADES:
            raise inv.ErrorInventario(f"Unidad desconocida: {unidad}")
        with self._transaccion() as cur:
            if self._fila(cur, "platos", plato_id) is None or self._fila(cur, "insumos", insumo_id) is None:
                return None
            return self._crear(cur, "plato_insumos",
                               {"plato_id": plato_id, "insumo_id": insumo_id, "cantidad": cantidad, "unidad": unidad})

    def set_unidad_ingrediente(self, rel_id, unidad):
        if unidad not in UNIDADES:
            raise inv.ErrorInventario(f"Unidad desconocida: {unidad}")
        with self._transaccion() as cur:
            fila = self._fila(cur, "plato_insumos", rel_id)
            if fila is not None:
                self._actualizar(cur, "plato_insumos", fila, {"unidad": unidad})

    def quitar_insumo_de_plato(self, rel_id):
        with self._transaccion() as cur:
            fila = self._fila(cur, "plato_insumos", rel_id)
            if fila is not None:
                self._eliminar(cur, "plato_insumos", fila)

    # ---------- INVENTARIO (provisional hasta sincronizar) ----------

    def _insumo_inventario(self, cur, insumo_id):
        fila = self._fila(cur, "insumos", insumo_id)
        if fila is None:
            raise inv.ErrorInventario("El insumo no existe o está eliminado")
        if fila["unidad_base"] is None:
            raise inv.ErrorInventario(
                f'El insumo "{fila["nombre"]}" no tiene unidad base confirmada: no lleva inventario')
        estado = inv.EstadoInventario(Decimal(fila["stock_actual"]), _dec(fila["costo_promedio"]),
                                      _dec(fila["costo_reposicion"]), _fecha(fila["costo_actualizado_en"]))
        return fila, estado

    def _guardar_estado(self, cur, insumo_id, e):
        # Igual que en el servidor: el inventario no sube la versión del insumo
        cur.execute(
            "UPDATE insumos SET stock_actual = ?, costo_promedio = ?, costo_reposicion = ?,"
            " costo_actualizado_en = ? WHERE id = ?",
            (str(e.stock_actual), _texto(e.costo_promedio), _texto(e.costo_reposicion),
             _iso(e.costo_actualizado_en) if e.costo_actualizado_en else None, insumo_id),
        )

    def set_unidad_base(self, insumo_id, unidad_base):
        """Confirma la unidad base de un insumo (D6: decisión explícita). No se cambia después."""
        if unidad_base not in BASES:
            raise inv.ErrorInventario("La unidad base debe ser g, ml o unidad")
        with self._transaccion() as cur:
            fila = self._fila(cur, "insumos", insumo_id)
            if fila is None:
                raise inv.ErrorInventario("El insumo no existe o está eliminado")
            if fila["unidad_base"] == unidad_base:
                return
            if fila["unidad_base"] is not None:
                raise inv.ErrorInventario("La unidad base de un insumo no se cambia")
            self._actualizar(cur, "insumos", fila, {"unidad_base": unidad_base})

    def registrar_compra(self, insumo_id, cantidad, unidad, costo_total, comprada_en=None):
        """Compra de `cantidad` `unidad` (p. ej. 25 kg) por `costo_total`. Devuelve el costo unitario."""
        comprada_en = comprada_en or datetime.now(timezone.utc)
        with self._transaccion() as cur:
            fila, estado = self._insumo_inventario(cur, insumo_id)
            en_base = inv.a_unidad_base(cantidad, unidad, fila["unidad_base"])
            if en_base is None:
                raise inv.ErrorInventario(f"La unidad {unidad} no corresponde a {fila['unidad_base']}")
            nuevo, unitario = inv.aplicar_compra(estado, en_base, costo_total, comprada_en)
            datos = {"uuid": str(uuid.uuid4()), "insumo_id": insumo_id, "cantidad_comprada": str(en_base),
                     "costo_total": str(inv.decimal(costo_total)), "costo_unitario": str(unitario),
                     "comprada_en": _iso(comprada_en)}
            cur.execute("INSERT INTO compras_insumos (uuid, insumo_id, cantidad_comprada, costo_total,"
                        " costo_unitario, comprada_en) VALUES (:uuid, :insumo_id, :cantidad_comprada,"
                        " :costo_total, :costo_unitario, :comprada_en)", datos)
            self._guardar_estado(cur, insumo_id, nuevo)
            self._encolar(cur, "compras_insumos", datos["uuid"], "crear", {
                "id": datos["uuid"], "insumo_uuid": fila["uuid"], "cantidad_comprada": datos["cantidad_comprada"],
                "costo_total": datos["costo_total"], "comprada_en": datos["comprada_en"]})
            return unitario

    def _consumir(self, cur, insumo_id, en_base, motivo, consumido_en, produccion_id=None):
        fila, estado = self._insumo_inventario(cur, insumo_id)
        r = inv.aplicar_consumo(estado, en_base, consumido_en)
        registro = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO consumos_insumos (uuid, insumo_id, produccion_id, cantidad, costo_unitario, costo_total,"
            " stock_resultante, stock_negativo, motivo, consumido_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (registro, insumo_id, produccion_id, str(inv.decimal(en_base)), _texto(r.costo_unitario),
             _texto(r.costo_total), str(r.estado.stock_actual), int(r.stock_negativo), motivo, _iso(consumido_en)))
        self._guardar_estado(cur, insumo_id, r.estado)
        return fila, registro, r

    def registrar_consumo(self, insumo_id, cantidad, unidad, motivo="consumo", consumido_en=None):
        """Descuenta stock al costo promedio. Devuelve el ResultadoConsumo (con el aviso de stock negativo)."""
        if motivo not in MOTIVOS_CONSUMO:
            raise inv.ErrorInventario("Motivo inválido (la producción se registra con registrar_produccion)")
        consumido_en = consumido_en or datetime.now(timezone.utc)
        with self._transaccion() as cur:
            fila = self._fila(cur, "insumos", insumo_id)
            en_base = inv.a_unidad_base(cantidad, unidad, fila["unidad_base"] if fila else None)
            if en_base is None:
                self._insumo_inventario(cur, insumo_id)       # da el error preciso si falta la base
                raise inv.ErrorInventario(f"La unidad {unidad} no corresponde a {fila['unidad_base']}")
            fila, registro, r = self._consumir(cur, insumo_id, en_base, motivo, consumido_en)
            self._encolar(cur, "consumos_insumos", registro, "crear", {
                "id": registro, "insumo_uuid": fila["uuid"], "cantidad": str(en_base), "motivo": motivo,
                "consumido_en": _iso(consumido_en)})
            return r

    def registrar_produccion(self, plato_id, porciones, producido_en=None):
        """Descuenta los ingredientes de `porciones` del plato. Devuelve el costo total (None si falta costo)."""
        producido_en = producido_en or datetime.now(timezone.utc)
        if inv.decimal(porciones) <= 0:
            raise inv.ErrorInventario("Las porciones deben ser mayores que cero")
        with self._transaccion() as cur:
            plato = self._fila(cur, "platos", plato_id)
            if plato is None:
                raise inv.ErrorInventario("El plato no existe o está eliminado")
            filas = cur.execute(
                "SELECT r.insumo_id, r.cantidad, r.unidad, i.unidad_base, i.merma_pct, i.uuid AS insumo_uuid"
                " FROM plato_insumos r JOIN insumos i ON i.id = r.insumo_id AND i.deleted_at IS NULL"
                " WHERE r.plato_id = ? AND r.deleted_at IS NULL ORDER BY i.uuid", (plato_id,)).fetchall()
            consumos = []
            for f in filas:
                cantidad = inv.cantidad_para_produccion(f["cantidad"], f["unidad"], f["unidad_base"],
                                                        porciones, f["merma_pct"])
                if cantidad is None:
                    raise inv.ErrorInventario("Hay ingredientes sin unidad confirmada o con unidades incompatibles")
                if cantidad > 0:
                    consumos.append((f["insumo_id"], cantidad))
            prod_uuid = str(uuid.uuid4())
            cur.execute("INSERT INTO producciones (uuid, plato_id, porciones, producido_en) VALUES (?, ?, ?, ?)",
                        (prod_uuid, plato_id, str(inv.decimal(porciones)), _iso(producido_en)))
            prod_id = cur.lastrowid
            total, falta_costo = Decimal("0"), False
            for insumo_id, cantidad in consumos:
                _f, _r, r = self._consumir(cur, insumo_id, cantidad, "produccion", producido_en, prod_id)
                if r.costo_total is None:
                    falta_costo = True
                else:
                    total += r.costo_total
            costo = None if falta_costo else total
            cur.execute("UPDATE producciones SET costo_total = ? WHERE id = ?", (_texto(costo), prod_id))
            # El servidor la aplica con registrar_produccion(id, plato, porciones): idempotente por id
            self._encolar(cur, "producciones", prod_uuid, "crear", {
                "id": prod_uuid, "plato_uuid": plato["uuid"], "porciones": str(inv.decimal(porciones)),
                "producido_en": _iso(producido_en)})
            return costo

    def actualizar_costo_reposicion(self, insumo_id, costo_unitario, vigente_desde=None):
        """Alza del proveedor sin compra física: cambia solo el costo de reposición y su fecha."""
        vigente_desde = vigente_desde or datetime.now(timezone.utc)
        with self._transaccion() as cur:
            fila, estado = self._insumo_inventario(cur, insumo_id)
            nuevo = inv.aplicar_costo_mercado(estado, costo_unitario, vigente_desde)
            self._guardar_estado(cur, insumo_id, nuevo)
            # Va a la cola aunque no cambie nada aquí: el servidor decide con su propio estado
            self._encolar(cur, "costos_reposicion", fila["uuid"], "actualizar", {
                "insumo_uuid": fila["uuid"], "costo_unitario": str(inv.decimal(costo_unitario)),
                "vigente_desde": _iso(vigente_desde)})

    def _provisional(self, insumo_id):
        """True si hay movimientos de este insumo que el servidor aún no confirmó."""
        return bool(self._con.execute(
            "SELECT EXISTS (SELECT 1 FROM cola_sync c WHERE c.estado <> 'sincronizada' AND ("
            " (c.tabla = 'compras_insumos' AND c.registro_uuid IN (SELECT uuid FROM compras_insumos WHERE insumo_id = :i))"
            " OR (c.tabla = 'consumos_insumos' AND c.registro_uuid IN (SELECT uuid FROM consumos_insumos WHERE insumo_id = :i))"
            " OR (c.tabla = 'producciones' AND c.registro_uuid IN (SELECT p.uuid FROM producciones p"
            "     JOIN consumos_insumos ci ON ci.produccion_id = p.id WHERE ci.insumo_id = :i))"
            " OR (c.tabla = 'costos_reposicion' AND c.registro_uuid = (SELECT uuid FROM insumos WHERE id = :i))))",
            {"i": insumo_id}).fetchone()[0])

    def inventario(self, insumo_id, ahora=None):
        """Estado del inventario de un insumo, con los avisos para el cotizador."""
        fila = self._con.execute("SELECT * FROM insumos WHERE id = ? AND deleted_at IS NULL", (insumo_id,)).fetchone()
        if fila is None:
            return None
        actualizado = _fecha(fila["costo_actualizado_en"])
        return {
            "id": fila["id"], "nombre": fila["nombre"], "unidad_base": fila["unidad_base"],
            "stock_actual": Decimal(fila["stock_actual"]), "costo_promedio": _dec(fila["costo_promedio"]),
            "costo_reposicion": _dec(fila["costo_reposicion"]), "costo_actualizado_en": actualizado,
            "sin_costo_reposicion": fila["costo_reposicion"] is None,
            "costo_desactualizado": costo_desactualizado(actualizado, ahora),
            "stock_negativo": Decimal(fila["stock_actual"]) < 0,
            "provisional": self._provisional(insumo_id),
        }

    def costo_proyectado(self, plato_id, ahora=None):
        """Costo para cotizar el plato con el costo de reposición (None si el plato no existe)."""
        plato = self.get_plato(plato_id)
        if plato is None:
            return None
        filas = self._con.execute(
            "SELECT i.nombre, r.cantidad, r.unidad, i.unidad_base, i.costo_reposicion, i.merma_pct,"
            " i.costo_actualizado_en, i.stock_actual FROM plato_insumos r"
            " JOIN insumos i ON i.id = r.insumo_id AND i.deleted_at IS NULL"
            " WHERE r.plato_id = ? AND r.deleted_at IS NULL ORDER BY r.id", (plato_id,)).fetchall()
        ingredientes = [{**dict(f), "costo_reposicion": _dec(f["costo_reposicion"]),
                         "costo_actualizado_en": _fecha(f["costo_actualizado_en"])} for f in filas]
        return costo_proyectado_plato(ingredientes, plato["mano_obra"], ahora)

    # ---------- COLA DE SINCRONIZACIÓN ----------

    def operaciones_pendientes(self, limite=50):
        """Las operaciones listas para enviar, en el orden en que ocurrieron."""
        filas = self._con.execute(
            "SELECT * FROM cola_sync WHERE estado IN ('pendiente', 'error') ORDER BY id LIMIT ?", (limite,)
        ).fetchall()
        return [{**dict(f), "datos": json.loads(f["datos"])} for f in filas]

    def marcar_operacion(self, op_uuid, estado, error=None):
        if estado not in ESTADOS_COLA:
            raise ValueError(f"Estado de cola desconocido: {estado}")
        with self._transaccion() as cur:
            suma = 1 if estado in ("error", "conflicto") else 0
            cur.execute(
                "UPDATE cola_sync SET estado = ?, ultimo_error = ?, intentos = intentos + ?, actualizada_en = ?"
                " WHERE op_uuid = ?",
                (estado, error, suma, _ahora_utc(), op_uuid),
            )
            if cur.rowcount != 1:
                raise KeyError(f"No existe la operación {op_uuid}")

    def resumen_cola(self):
        """Cantidad de operaciones por estado (para mostrar 'N cambios pendientes')."""
        conteo = {estado: 0 for estado in ESTADOS_COLA}
        for fila in self._con.execute("SELECT estado, COUNT(*) FROM cola_sync GROUP BY estado"):
            conteo[fila[0]] = fila[1]
        return conteo


class _Transaccion:
    """BEGIN IMMEDIATE … COMMIT, con ROLLBACK si algo falla dentro del bloque."""

    def __init__(self, con):
        self._con = con

    def __enter__(self):
        self._cur = self._con.cursor()
        self._cur.execute("BEGIN IMMEDIATE")
        return self._cur

    def __exit__(self, tipo, valor, traza):
        self._cur.execute("COMMIT" if tipo is None else "ROLLBACK")
        self._cur.close()
        return False


def ruta_base(datos_dir):
    """Ubicación prevista: junto a los demás datos, en <user_data_dir>/datos/smartcost.db."""
    return os.path.join(datos_dir, NOMBRE_ARCHIVO)
