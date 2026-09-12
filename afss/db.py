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

CREATE TABLE IF NOT EXISTS studios(
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    tags_json TEXT
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

    transcoded_path TEXT,
    transcoded_at TEXT,
    transcode_verified INTEGER DEFAULT 0,

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
    collection_override TEXT,
    UNIQUE(profile_id, folder_name, folder_level)
);

CREATE TABLE IF NOT EXISTS trash_folder_names(
    name_normalized TEXT PRIMARY KEY,
    name_raw TEXT,
    added_at TEXT
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

CREATE TABLE IF NOT EXISTS media_item_co_artists(
    media_item_id INTEGER REFERENCES media_items(id),
    artist_id TEXT REFERENCES artists(id),
    PRIMARY KEY (media_item_id, artist_id)
);

CREATE TABLE IF NOT EXISTS sort_studio_locks(
    artist_key TEXT PRIMARY KEY,
    locked_at TEXT
);
"""


def get_db_path() -> Path:
    return DB_PATH


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or DB_PATH), timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL erlaubt gleichzeitige Leser während ein Schreiber aktiv ist (Dashboard + parallele
    # Aktionen greifen sonst leicht in "database is locked", v.a. bei größeren Profilen).
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Fügt Spalten hinzu, die nach dem ersten Release ergänzt wurden - CREATE TABLE IF NOT
    EXISTS rührt bestehende Tabellen nicht an, daher hier ein leichtgewichtiger ALTER TABLE."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(unresolved_folders)")
    columns = {row[1] for row in cur.fetchall()}
    if "collection_override" not in columns:
        cur.execute("ALTER TABLE unresolved_folders ADD COLUMN collection_override TEXT")

    cur.execute("PRAGMA table_info(media_items)")
    columns = {row[1] for row in cur.fetchall()}
    if "transcoded_path" not in columns:
        cur.execute("ALTER TABLE media_items ADD COLUMN transcoded_path TEXT")
    if "transcoded_at" not in columns:
        cur.execute("ALTER TABLE media_items ADD COLUMN transcoded_at TEXT")
    if "transcode_verified" not in columns:
        cur.execute("ALTER TABLE media_items ADD COLUMN transcode_verified INTEGER DEFAULT 0")
    if "manual_override" not in columns:
        cur.execute("ALTER TABLE media_items ADD COLUMN manual_override INTEGER DEFAULT 0")
    if "title_override" not in columns:
        cur.execute("ALTER TABLE media_items ADD COLUMN title_override TEXT")
    if "item_status" not in columns:
        cur.execute("ALTER TABLE media_items ADD COLUMN item_status TEXT DEFAULT 'active'")
    if "tags" not in columns:
        cur.execute("ALTER TABLE media_items ADD COLUMN tags TEXT")
    if "studio_id" not in columns:
        cur.execute("ALTER TABLE media_items ADD COLUMN studio_id TEXT REFERENCES studios(id)")


def init_schema(db_path: Path | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        _migrate_schema(conn)
        conn.commit()
    finally:
        conn.close()
