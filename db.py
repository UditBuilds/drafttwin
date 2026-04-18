import os
import sqlite3
from flask import g

DB_PATH = os.environ.get("DRAFTTWIN_DB", "drafttwin.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS brands (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    email          TEXT UNIQUE,
    password_hash  TEXT,
    name           TEXT,
    brain_md       TEXT,
    form_json      TEXT,
    version        TEXT NOT NULL DEFAULT '1.0',
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drafts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id       INTEGER NOT NULL REFERENCES brands(id),
    customer_msg   TEXT NOT NULL,
    classification TEXT NOT NULL,
    reply          TEXT NOT NULL,
    reasoning      TEXT,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS flagged_drafts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id        INTEGER NOT NULL UNIQUE REFERENCES drafts(id),
    brand_id        INTEGER NOT NULL REFERENCES brands(id),
    suggested_reply TEXT NOT NULL,
    resolved        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_drafts_brand_id   ON drafts(brand_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_flags_brand_id    ON flagged_drafts(brand_id, id DESC);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _columns(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _ensure_column(conn, table, col, ddl):
    if col not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    # Migrations for Phase 1 DBs that predate auth/versioning.
    _ensure_column(conn, "brands", "email", "TEXT")
    _ensure_column(conn, "brands", "password_hash", "TEXT")
    _ensure_column(conn, "brands", "version", "TEXT NOT NULL DEFAULT '1.0'")
    conn.commit()
    conn.close()


# --- Brand / user helpers ---------------------------------------------------

def get_brand_by_email(email):
    return get_db().execute(
        "SELECT * FROM brands WHERE email = ?", (email,)
    ).fetchone()


def get_brand(brand_id):
    return get_db().execute(
        "SELECT * FROM brands WHERE id = ?", (brand_id,)
    ).fetchone()


def create_account(email, password_hash):
    db = get_db()
    cur = db.execute(
        "INSERT INTO brands (email, password_hash) VALUES (?, ?)",
        (email, password_hash),
    )
    db.commit()
    return cur.lastrowid


def save_brand_onboarding(brand_id, name, brain_md, form_json):
    db = get_db()
    db.execute(
        """UPDATE brands
           SET name = ?, brain_md = ?, form_json = ?, version = '1.0',
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (name, brain_md, form_json, brand_id),
    )
    db.commit()


def update_brain(brand_id, brain_md, version):
    db = get_db()
    db.execute(
        """UPDATE brands
           SET brain_md = ?, version = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (brain_md, version, brand_id),
    )
    db.commit()


# --- Drafts -----------------------------------------------------------------

def save_draft(brand_id, customer_msg, classification, reply, reasoning):
    db = get_db()
    cur = db.execute(
        """INSERT INTO drafts
           (brand_id, customer_msg, classification, reply, reasoning)
           VALUES (?, ?, ?, ?, ?)""",
        (brand_id, customer_msg, classification, reply, reasoning),
    )
    db.commit()
    return cur.lastrowid


def recent_drafts(brand_id, limit=20):
    return get_db().execute(
        """SELECT d.*, f.id AS flag_id, f.suggested_reply, f.resolved
           FROM drafts d
           LEFT JOIN flagged_drafts f ON f.draft_id = d.id
           WHERE d.brand_id = ?
           ORDER BY d.id DESC
           LIMIT ?""",
        (brand_id, limit),
    ).fetchall()


def get_draft(draft_id, brand_id):
    return get_db().execute(
        "SELECT * FROM drafts WHERE id = ? AND brand_id = ?",
        (draft_id, brand_id),
    ).fetchone()


# --- Flags ------------------------------------------------------------------

def upsert_flag(draft_id, brand_id, suggested_reply):
    """Insert a flag for this draft, or update the existing one."""
    db = get_db()
    db.execute(
        """INSERT INTO flagged_drafts (draft_id, brand_id, suggested_reply)
           VALUES (?, ?, ?)
           ON CONFLICT(draft_id) DO UPDATE SET
               suggested_reply = excluded.suggested_reply,
               resolved = 0,
               updated_at = CURRENT_TIMESTAMP""",
        (draft_id, brand_id, suggested_reply),
    )
    db.commit()


def resolve_flag(flag_id, brand_id):
    db = get_db()
    db.execute(
        """UPDATE flagged_drafts SET resolved = 1, updated_at = CURRENT_TIMESTAMP
           WHERE id = ? AND brand_id = ?""",
        (flag_id, brand_id),
    )
    db.commit()


def delete_flag(flag_id, brand_id):
    db = get_db()
    db.execute(
        "DELETE FROM flagged_drafts WHERE id = ? AND brand_id = ?",
        (flag_id, brand_id),
    )
    db.commit()


def flagged_drafts_for_brand(brand_id, include_resolved=True):
    q = """SELECT f.*, d.customer_msg, d.classification, d.reply AS original_reply, d.created_at AS draft_at
           FROM flagged_drafts f
           JOIN drafts d ON d.id = f.draft_id
           WHERE f.brand_id = ?"""
    if not include_resolved:
        q += " AND f.resolved = 0"
    q += " ORDER BY f.resolved ASC, f.id DESC"
    return get_db().execute(q, (brand_id,)).fetchall()
