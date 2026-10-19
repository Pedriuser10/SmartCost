"""
Capa de persistencia - SQLite
Tablas: insumos, platos, plato_insumos
"""
import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "app.db"
)


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS insumos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            unidad TEXT NOT NULL,
            precio REAL NOT NULL,
            merma_pct REAL NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS platos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio_venta REAL NOT NULL,
            mano_obra REAL NOT NULL DEFAULT 0,
            imagen TEXT
        )
    """)

    # Migración: si la tabla ya existía sin la columna 'imagen', se agrega ahora.
    try:
        cur.execute("ALTER TABLE platos ADD COLUMN imagen TEXT")
    except sqlite3.OperationalError:
        pass  # la columna ya existe

    cur.execute("""
        CREATE TABLE IF NOT EXISTS plato_insumos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plato_id INTEGER NOT NULL,
            insumo_id INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            FOREIGN KEY (plato_id) REFERENCES platos(id) ON DELETE CASCADE,
            FOREIGN KEY (insumo_id) REFERENCES insumos(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()
    seed_if_empty()


def seed_if_empty():
    """Carga datos de ejemplo la primera vez que se abre la app."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM insumos")
    if cur.fetchone()["c"] == 0:
        insumos_demo = [
            ("Carne molida", "kg", 6500, 0.05),
            ("Pan hamburguesa", "un", 350, 0.02),
            ("Queso gauda", "kg", 7800, 0.03),
            ("Tomate", "kg", 1200, 0.10),
            ("Lechuga", "un", 900, 0.08),
        ]
        cur.executemany(
            "INSERT INTO insumos (nombre, unidad, precio, merma_pct) VALUES (?, ?, ?, ?)",
            insumos_demo,
        )
        conn.commit()

        cur.execute("SELECT id, nombre FROM insumos")
        ids = {row["nombre"]: row["id"] for row in cur.fetchall()}

        cur.execute(
            "INSERT INTO platos (nombre, precio_venta, mano_obra) VALUES (?, ?, ?)",
            ("Hamburguesa Clásica", 4500, 800),
        )
        plato_id = cur.lastrowid
        receta = [
            (plato_id, ids["Carne molida"], 0.15),
            (plato_id, ids["Pan hamburguesa"], 1),
            (plato_id, ids["Queso gauda"], 0.03),
            (plato_id, ids["Tomate"], 0.03),
            (plato_id, ids["Lechuga"], 0.2),
        ]
        cur.executemany(
            "INSERT INTO plato_insumos (plato_id, insumo_id, cantidad) VALUES (?, ?, ?)",
            receta,
        )
        conn.commit()
    conn.close()


# ---------- INSUMOS ----------

def get_insumos():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM insumos ORDER BY nombre").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_insumo(nombre, unidad, precio, merma_pct):
    conn = get_connection()
    conn.execute(
        "INSERT INTO insumos (nombre, unidad, precio, merma_pct) VALUES (?, ?, ?, ?)",
        (nombre, unidad, precio, merma_pct),
    )
    conn.commit()
    conn.close()


def update_insumo(insumo_id, nombre, unidad, precio, merma_pct):
    conn = get_connection()
    conn.execute(
        "UPDATE insumos SET nombre=?, unidad=?, precio=?, merma_pct=? WHERE id=?",
        (nombre, unidad, precio, merma_pct, insumo_id),
    )
    conn.commit()
    conn.close()


def delete_insumo(insumo_id):
    conn = get_connection()
    conn.execute("DELETE FROM insumos WHERE id = ?", (insumo_id,))
    conn.commit()
    conn.close()


# ---------- PLATOS ----------

def get_platos():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM platos ORDER BY nombre").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plato(plato_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM platos WHERE id = ?", (plato_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_insumos_de_plato(plato_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT pi.id as rel_id, pi.cantidad, i.*
        FROM plato_insumos pi
        JOIN insumos i ON i.id = pi.insumo_id
        WHERE pi.plato_id = ?
        """,
        (plato_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_plato(nombre, precio_venta, mano_obra, imagen=None):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO platos (nombre, precio_venta, mano_obra, imagen) VALUES (?, ?, ?, ?)",
        (nombre, precio_venta, mano_obra, imagen),
    )
    conn.commit()
    plato_id = cur.lastrowid
    conn.close()
    return plato_id


def update_plato(plato_id, nombre, precio_venta, mano_obra, imagen=None):
    conn = get_connection()
    if imagen is not None:
        conn.execute(
            "UPDATE platos SET nombre=?, precio_venta=?, mano_obra=?, imagen=? WHERE id=?",
            (nombre, precio_venta, mano_obra, imagen, plato_id),
        )
    else:
        # No se tocó la imagen: se actualiza todo menos ese campo.
        conn.execute(
            "UPDATE platos SET nombre=?, precio_venta=?, mano_obra=? WHERE id=?",
            (nombre, precio_venta, mano_obra, plato_id),
        )
    conn.commit()
    conn.close()


def delete_plato(plato_id):
    conn = get_connection()
    conn.execute("DELETE FROM platos WHERE id = ?", (plato_id,))
    conn.commit()
    conn.close()


def add_insumo_a_plato(plato_id, insumo_id, cantidad):
    conn = get_connection()
    conn.execute(
        "INSERT INTO plato_insumos (plato_id, insumo_id, cantidad) VALUES (?, ?, ?)",
        (plato_id, insumo_id, cantidad),
    )
    conn.commit()
    conn.close()


def quitar_insumo_de_plato(rel_id):
    conn = get_connection()
    conn.execute("DELETE FROM plato_insumos WHERE id = ?", (rel_id,))
    conn.commit()
    conn.close()