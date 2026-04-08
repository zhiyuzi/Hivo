import sqlite3
import os
from contextlib import contextmanager
from .config import settings


def init_db(db_path: str | None = None) -> None:
    path = db_path or settings.database_path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with sqlite3.connect(path) as conn:
        # Migration: add display_name and bio to existing memberships tables
        for col in ("display_name TEXT", "bio TEXT"):
            try:
                conn.execute(f"ALTER TABLE memberships ADD COLUMN {col}")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clubs (
                club_id     TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT,
                owner_sub   TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memberships (
                id           TEXT PRIMARY KEY,
                club_id      TEXT NOT NULL REFERENCES clubs(club_id),
                sub          TEXT NOT NULL,
                role         TEXT NOT NULL,
                display_name TEXT,
                bio          TEXT,
                note         TEXT,
                invited_by   TEXT NOT NULL,
                joined_at    TEXT NOT NULL,

                UNIQUE(club_id, sub)
            );

            CREATE INDEX IF NOT EXISTS idx_memberships_club_sub
                ON memberships(club_id, sub);

            CREATE TABLE IF NOT EXISTS invite_links (
                token       TEXT PRIMARY KEY,
                club_id     TEXT NOT NULL REFERENCES clubs(club_id),
                role        TEXT NOT NULL DEFAULT 'member',
                created_by  TEXT NOT NULL,
                max_uses    INTEGER,
                use_count   INTEGER NOT NULL DEFAULT 0,
                expires_at  TEXT,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_invite_links_club
                ON invite_links(club_id);

            CREATE TABLE IF NOT EXISTS club_files (
                id              TEXT PRIMARY KEY,
                club_id         TEXT NOT NULL REFERENCES clubs(club_id),
                file_id         TEXT NOT NULL,
                owner_sub       TEXT NOT NULL,
                alias           TEXT NOT NULL,
                permissions     TEXT NOT NULL DEFAULT 'read',
                contributed_by  TEXT NOT NULL,
                added_at        TEXT NOT NULL,

                UNIQUE(club_id, alias),
                UNIQUE(club_id, file_id)
            );

            CREATE INDEX IF NOT EXISTS idx_club_files_club
                ON club_files(club_id);
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
