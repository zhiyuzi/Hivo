import sqlite3
import os
from contextlib import contextmanager
from .config import settings


def init_db(db_path: str | None = None) -> None:
    path = db_path or settings.database_path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS salons (
                id          TEXT PRIMARY KEY,
                club_id     TEXT NOT NULL,
                name        TEXT NOT NULL,
                bulletin    TEXT,
                owner_sub   TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS salon_members (
                id           TEXT PRIMARY KEY,
                salon_id     TEXT NOT NULL REFERENCES salons(id),
                sub          TEXT NOT NULL,
                role         TEXT NOT NULL,
                display_name TEXT,
                bio          TEXT,
                joined_at    TEXT NOT NULL,

                UNIQUE(salon_id, sub)
            );

            CREATE INDEX IF NOT EXISTS idx_salon_members_salon_sub
                ON salon_members(salon_id, sub);

            CREATE TABLE IF NOT EXISTS messages (
                id          TEXT PRIMARY KEY,
                salon_id    TEXT NOT NULL REFERENCES salons(id),
                sender_sub  TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_salon_created
                ON messages(salon_id, created_at);

            CREATE TABLE IF NOT EXISTS salon_files (
                id          TEXT PRIMARY KEY,
                salon_id    TEXT NOT NULL REFERENCES salons(id),
                file_id     TEXT NOT NULL,
                owner_sub   TEXT NOT NULL,
                alias       TEXT NOT NULL,
                permissions TEXT NOT NULL DEFAULT 'read',
                added_at    TEXT NOT NULL,

                UNIQUE(salon_id, alias),
                UNIQUE(salon_id, file_id)
            );

            CREATE TABLE IF NOT EXISTS read_cursors (
                id           TEXT PRIMARY KEY,
                salon_id     TEXT NOT NULL REFERENCES salons(id),
                sub          TEXT NOT NULL,
                last_read_at TEXT NOT NULL,

                UNIQUE(salon_id, sub)
            );

            CREATE INDEX IF NOT EXISTS idx_read_cursors_salon_sub
                ON read_cursors(salon_id, sub);
        """)


@contextmanager
def get_conn(db_path: str | None = None):
    path = db_path or settings.database_path
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
