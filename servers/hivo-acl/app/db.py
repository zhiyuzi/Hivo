import sqlite3
import os
from contextlib import contextmanager
from .config import settings


def init_db(db_path: str | None = None) -> None:
    path = db_path or settings.database_path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS grants (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject     TEXT NOT NULL,
                resource    TEXT NOT NULL,
                action      TEXT NOT NULL,
                effect      TEXT NOT NULL DEFAULT 'allow',
                granted_by  TEXT NOT NULL,
                created_at  TEXT NOT NULL,

                UNIQUE(subject, resource, action, effect)
            );

            CREATE INDEX IF NOT EXISTS idx_grants_subject_resource_action
                ON grants(subject, resource, action);
            CREATE INDEX IF NOT EXISTS idx_grants_subject_action
                ON grants(subject, action);
            CREATE INDEX IF NOT EXISTS idx_grants_resource
                ON grants(resource);
            CREATE INDEX IF NOT EXISTS idx_grants_granted_by
                ON grants(granted_by);

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event       TEXT NOT NULL,
                subject     TEXT NOT NULL,
                resource    TEXT NOT NULL,
                action      TEXT NOT NULL,
                actor       TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );
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
