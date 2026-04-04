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
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id           TEXT PRIMARY KEY,
                owner_sub    TEXT NOT NULL,
                owner_iss    TEXT NOT NULL,
                path         TEXT NOT NULL,
                r2_key       TEXT NOT NULL,
                content_type TEXT NOT NULL,
                visibility   TEXT NOT NULL DEFAULT 'private',
                share_id     TEXT UNIQUE,
                size         INTEGER NOT NULL,
                sha256       TEXT NOT NULL,
                etag         TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL,

                UNIQUE(owner_iss, owner_sub, path)
            );

            CREATE INDEX IF NOT EXISTS idx_files_owner
                ON files(owner_iss, owner_sub, path);

            CREATE INDEX IF NOT EXISTS idx_files_share
                ON files(share_id);

            CREATE INDEX IF NOT EXISTS idx_files_visibility
                ON files(owner_iss, owner_sub, visibility);
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
