import sqlite3
import os
from contextlib import contextmanager
from .config import settings


def get_db_path() -> str:
    return settings.database_path


def init_db(db_path: str | None = None) -> None:
    path = db_path or get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with sqlite3.connect(path) as conn:
        # Migration: add audience column to existing DBs
        try:
            conn.execute("ALTER TABLE refresh_tokens ADD COLUMN audience TEXT NOT NULL DEFAULT ''")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS subjects (
                sub          TEXT PRIMARY KEY,
                handle       TEXT NOT NULL UNIQUE,
                email        TEXT,
                display_name TEXT,
                status       TEXT NOT NULL DEFAULT 'active',
                jwk_pub      TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS signing_keys (
                kid         TEXT PRIMARY KEY,
                alg         TEXT NOT NULL,
                private_key TEXT NOT NULL,
                public_key  TEXT NOT NULL,
                is_current  INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pending_registrations (
                challenge  TEXT PRIMARY KEY,
                handle     TEXT NOT NULL,
                jwk_pub    TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                sub        TEXT NOT NULL,
                audience   TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)


@contextmanager
def get_conn(db_path: str | None = None):
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
