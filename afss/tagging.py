from pathlib import Path

from afss.db import get_connection
from afss.normalize import normalize_name

_KIND_TABLES = {
    "artist": ("artists", "artist_aliases", "artist_id", "assigned_artist"),
    "provider": ("providers", "provider_aliases", "provider_id", "assigned_provider"),
}


def _kind_tables(kind: str):
    if kind not in _KIND_TABLES:
        raise ValueError(f"Unbekannter kind: {kind}")
    return _KIND_TABLES[kind]


def _unique_entity_id(cur, table: str, canonical_name: str) -> str:
    base = normalize_name(canonical_name) or "entity"
    candidate = base
    suffix = 1
    while True:
        cur.execute(f"SELECT 1 FROM {table} WHERE id = ?", (candidate,))
        if cur.fetchone() is None:
            return candidate
        suffix += 1
        candidate = f"{base}_{suffix}"


def _add_alias_safe(cur, alias_table: str, fk_col: str, entity_id: str, alias_raw: str) -> dict | None:
    alias = normalize_name(alias_raw)
    if not alias:
        return None
    cur.execute(f"SELECT {fk_col} FROM {alias_table} WHERE alias = ?", (alias,))
    row = cur.fetchone()
    if row and row[0] != entity_id:
        return {"alias": alias, "alias_raw": alias_raw, "conflict_with": row[0]}
    cur.execute(
        f"INSERT OR IGNORE INTO {alias_table}(alias, alias_raw, {fk_col}) VALUES (?, ?, ?)",
        (alias, alias_raw, entity_id),
    )
    return None


def get_pending_unresolved(profile_id: str, db_path: Path | None = None) -> list[tuple]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, folder_name, folder_level, occurrence_count, sample_path
        FROM unresolved_folders
        WHERE profile_id = ? AND status = 'pending'
        ORDER BY occurrence_count DESC
        """,
        (profile_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def search_entities(kind: str, query: str, db_path: Path | None = None) -> list[tuple]:
    table = _kind_tables(kind)[0]
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        f"SELECT id, canonical_name FROM {table} WHERE canonical_name LIKE ? ORDER BY canonical_name LIMIT 25",
        (f"%{query}%",),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def assign_to_new_entity(
    unresolved_id: int,
    kind: str,
    canonical_name: str,
    db_path: Path | None = None,
    collection_override: str | None = None,
) -> tuple[str, dict | None]:
    table, alias_table, fk_col, status = _kind_tables(kind)
    conn = get_connection(db_path)
    cur = conn.cursor()

    entity_id = _unique_entity_id(cur, table, canonical_name)
    cur.execute(
        f"INSERT INTO {table}(id, canonical_name, tags_json) VALUES (?, ?, NULL)",
        (entity_id, canonical_name),
    )

    cur.execute("SELECT folder_name FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"unresolved_folders id nicht gefunden: {unresolved_id}")
    folder_name = row[0]

    conflict = _add_alias_safe(cur, alias_table, fk_col, entity_id, folder_name)

    cur.execute(
        "UPDATE unresolved_folders SET status = ?, resolved_to_id = ?, collection_override = ? WHERE id = ?",
        (status, entity_id, collection_override or None, unresolved_id),
    )
    conn.commit()
    conn.close()
    return entity_id, conflict


def assign_to_existing_entity(
    unresolved_id: int,
    kind: str,
    entity_id: str,
    db_path: Path | None = None,
    collection_override: str | None = None,
) -> dict | None:
    _, alias_table, fk_col, status = _kind_tables(kind)
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT folder_name FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"unresolved_folders id nicht gefunden: {unresolved_id}")
    folder_name = row[0]

    conflict = _add_alias_safe(cur, alias_table, fk_col, entity_id, folder_name)

    cur.execute(
        "UPDATE unresolved_folders SET status = ?, resolved_to_id = ?, collection_override = ? WHERE id = ?",
        (status, entity_id, collection_override or None, unresolved_id),
    )
    conn.commit()
    conn.close()
    return conflict


def ignore_folder(unresolved_id: int, db_path: Path | None = None) -> None:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE unresolved_folders SET status = 'ignored', resolved_to_id = NULL WHERE id = ?",
        (unresolved_id,),
    )
    conn.commit()
    conn.close()


def set_category(unresolved_id: int, db_path: Path | None = None) -> None:
    """Markiert einen Ordner als legitime Kategorie (z.B. 'Chat', 'Pics') - kein Artist/Provider,
    aber auch kein Datenmüll. Taucht danach nicht mehr in der pending-Liste auf."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE unresolved_folders SET status = 'category', resolved_to_id = NULL WHERE id = ?",
        (unresolved_id,),
    )
    conn.commit()
    conn.close()


def set_trash(unresolved_id: int, db_path: Path | None = None) -> None:
    """Markiert einen Ordner als Datenmüll UND merkt sich den Namen global, damit scan.py
    diesen Ordnernamen ab sofort auf allen Profilen automatisch überspringt."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT folder_name FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"unresolved_folders id nicht gefunden: {unresolved_id}")
    folder_name = row[0]

    cur.execute(
        "INSERT OR IGNORE INTO trash_folder_names(name_normalized, name_raw, added_at) VALUES (?, ?, datetime('now'))",
        (normalize_name(folder_name), folder_name),
    )
    cur.execute(
        "UPDATE unresolved_folders SET status = 'trash', resolved_to_id = NULL WHERE id = ?",
        (unresolved_id,),
    )
    conn.commit()
    conn.close()


def get_trash_folder_names(db_path: Path | None = None) -> set[str]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name_normalized FROM trash_folder_names")
    names = {r[0] for r in cur.fetchall()}
    conn.close()
    return names


def get_collection_overrides(profile_id: str, db_path: Path | None = None) -> dict[tuple[str, int], str]:
    """Liefert {(folder_name, folder_level): collection_name}, manuell beim Taggen erfasst -
    z.B. wenn ein Ordnername Artist und Collection kombiniert ('Artist Shoot2025')."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT folder_name, folder_level, collection_override FROM unresolved_folders
        WHERE profile_id = ? AND collection_override IS NOT NULL AND collection_override != ''
        """,
        (profile_id,),
    )
    overrides = {(name, level): override for name, level, override in cur.fetchall()}
    conn.close()
    return overrides
