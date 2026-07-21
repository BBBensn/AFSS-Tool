import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "afss.db"


def get_db_path() -> Path:
    return DB_PATH


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_schema() -> None:
    """Create required tables if they do not exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS artists(
            id TEXT PRIMARY KEY,
            canonical_name TEXT,
            raw_data TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS providers(
            id TEXT PRIMARY KEY,
            name TEXT,
            raw_data TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS media_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            media_type TEXT,
            artist_id TEXT NULL,
            provider_id TEXT NULL,
            collection_name TEXT NULL,
            legacy_profile_id TEXT,
            origin_hint TEXT NULL,
            fs_created_at TEXT NULL,
            fs_modified_at TEXT NULL,
            imported_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()
