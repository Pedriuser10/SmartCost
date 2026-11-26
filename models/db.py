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

Fuera de esta fase, a propósito:
- Migrar los JSON actuales (D3 y D6 exigen informe y confirmación caso por caso).
- Supabase, negocios, roles y resolución de conflictos.
- Precisión decimal y catálogo de unidades (pendientes de 8.10).
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

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
]

VERSION_ESQUEMA = len(_MIGRACIONES)


def _ahora_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _ahora_local():
    # Mismo formato que fecha_creacion en el JSON actual
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clave_nombre(fila):
    return fila["nombre"].lower()


class EsquemaMasNuevo(RuntimeError):
    """La base fue creada por una versión más nueva de la app: no se toca."""


class BaseLocal:
    def __init__(self, ruta):
        self.ruta = ruta
        self._con = sqlite3.connect(ruta, isolation_level=None)  # transacciones explícitas
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.execute("PRAGMA journal_mode = WAL")
        self._con.execute("PRAGMA synchronous = FULL")
        self._migrar()
        self._recuperar_en_proceso()

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

    def add_insumo_a_plato(self, plato_id, insumo_id, cantidad):
        """Devuelve el rel_id nuevo, o None si el plato o el insumo no existen."""
        with self._transaccion() as cur:
            if self._fila(cur, "platos", plato_id) is None or self._fila(cur, "insumos", insumo_id) is None:
                return None
            return self._crear(cur, "plato_insumos",
                               {"plato_id": plato_id, "insumo_id": insumo_id, "cantidad": cantidad})

    def quitar_insumo_de_plato(self, rel_id):
        with self._transaccion() as cur:
            fila = self._fila(cur, "plato_insumos", rel_id)
            if fila is not None:
                self._eliminar(cur, "plato_insumos", fila)

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
