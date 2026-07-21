import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "afss.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles(
    id TEXT PRIMARY KEY,
    description TEXT,
    root_path TEXT NOT NULL,
    disk_label TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS artists(
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    tags_json TEXT
);

CREATE TABLE IF NOT EXISTS artist_aliases(
    alias TEXT PRIMARY KEY,
    alias_raw TEXT,
    artist_id TEXT NOT NULL REFERENCES artists(id)
);

CREATE TABLE IF NOT EXISTS providers(
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    tags_json TEXT
);

CREATE TABLE IF NOT EXISTS provider_aliases(
    alias TEXT PRIMARY KEY,
    alias_raw TEXT,
    provider_id TEXT NOT NULL REFERENCES providers(id)
);

CREATE TABLE IF NOT EXISTS media_items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profiles(id),
    path TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    ext TEXT,
    media_type TEXT,
    size_bytes INTEGER,
    file_hash TEXT,
    fs_created_at TEXT,
    fs_modified_at TEXT,

    folder_level1 TEXT,
    folder_level2 TEXT,

    artist_id TEXT REFERENCES artists(id),
    provider_id TEXT REFERENCES providers(id),
    collection_name TEXT,

    planned_filename TEXT,
    needs_review INTEGER DEFAULT 0,
    review_reason TEXT,

    target_path TEXT,
    applied_at TEXT,
    verified INTEGER DEFAULT 0,

    scanned_at TEXT NOT NULL,
    UNIQUE(profile_id, rel_path)
);

CREATE TABLE IF NOT EXISTS unresolved_folders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    folder_name TEXT NOT NULL,
    folder_level INTEGER,
    occurrence_count INTEGER,
    sample_path TEXT,
    status TEXT DEFAULT 'pending',
    resolved_to_id TEXT,
    UNIQUE(profile_id, folder_name, folder_level)
);

CREATE TABLE IF NOT EXISTS dedupe_groups(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    kept_media_item_id INTEGER REFERENCES media_items(id),
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS dedupe_group_members(
    dedupe_group_id INTEGER REFERENCES dedupe_groups(id),
    media_item_id INTEGER REFERENCES media_items(id),
    action TEXT DEFAULT 'pending'
);
"""


def get_db_path() -> Path:
    return DB_PATH


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(db_path: Path | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
