from pathlib import Path

from afss.db import get_connection
from afss.tagging import get_json_canonical_name

_ALLOWED_BULK_FIELDS = {"artist_id", "provider_id", "collection_name"}
_TABLE_BY_FIELD = {"artist_id": ("artists", "artist"), "provider_id": ("providers", "provider")}


def _ensure_entity_in_db(cur, field: str, entity_id: str, config_dir: Path) -> None:
    """media_items.artist_id/provider_id haben eine FK auf artists/providers - ein Artist, der
    bisher nur in artists.json existiert (z.B. über den Artist-Editor angelegt, siehe die
    Such-Lücke die das ausgelöst hat), muss vor dem Zuweisen erst als DB-Zeile nachgezogen werden,
    sonst schlägt das UPDATE mit einem FK-Constraint-Fehler fehl."""
    table, kind = _TABLE_BY_FIELD[field]
    cur.execute(f"SELECT 1 FROM {table} WHERE id = ?", (entity_id,))
    if cur.fetchone() is not None:
        return
    canonical_name = get_json_canonical_name(kind, entity_id, config_dir) or entity_id
    cur.execute(f"INSERT INTO {table}(id, canonical_name, tags_json) VALUES (?, ?, NULL)", (entity_id, canonical_name))


def get_profile_tree(profile_id: str, db_path: Path | None = None) -> dict:
    """Liefert alle media_items eines Profils gruppiert nach Artist -> Collection, für die
    manuelle Sortier-Studio-Ansicht. Dateien, die bereits als Duplikat zum Löschen/Behalten
    markiert wurden (dedupe_group_members.action in pending/delete), werden ausgeblendet - die
    sind nicht Teil dessen, was der Nutzer noch manuell einsortieren muss."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.id, m.filename, m.rel_path, m.media_type, m.artist_id, a.canonical_name,
               m.provider_id, p.canonical_name, m.collection_name, m.title_override, m.manual_override
        FROM media_items m
        LEFT JOIN artists a ON a.id = m.artist_id
        LEFT JOIN providers p ON p.id = m.provider_id
        LEFT JOIN dedupe_group_members dgm ON dgm.media_item_id = m.id AND dgm.action IN ('pending', 'delete')
        WHERE m.profile_id = ? AND dgm.media_item_id IS NULL
        ORDER BY a.canonical_name IS NULL, a.canonical_name, m.collection_name IS NULL, m.collection_name, m.filename
        """,
        (profile_id,),
    )
    rows = cur.fetchall()
    conn.close()

    artists: dict[str, dict] = {}
    for (
        item_id, filename, rel_path, media_type, artist_id, artist_name,
        provider_id, provider_name, collection_name, title_override, manual_override,
    ) in rows:
        artist_key = artist_id or "_unresolved"
        artist_entry = artists.setdefault(
            artist_key,
            {"artist_id": artist_id, "artist_name": artist_name or "(kein Artist zugeordnet)", "collections": {}},
        )
        collection_key = collection_name or "_none"
        entry = artist_entry["collections"].setdefault(collection_key, {"collection_name": collection_name, "files": []})
        entry["files"].append(
            {
                "id": item_id,
                "filename": filename,
                "rel_path": rel_path,
                "media_type": media_type,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "title_override": title_override,
                "manual_override": bool(manual_override),
            }
        )

    return artists


def bulk_update(
    item_ids: list[int], fields: dict, db_path: Path | None = None, config_dir: Path | None = None
) -> int:
    """Setzt artist_id/provider_id/collection_name für mehrere media_items auf einmal (auch auf
    None zum Zurücksetzen - daher Schlüssel-Präsenz statt Wahrheitswert prüfen) und markiert sie
    als manual_override=1, damit ein späteres 'resolve' diese Entscheidung nicht überschreibt."""
    fields = {k: v for k, v in fields.items() if k in _ALLOWED_BULK_FIELDS}
    if not fields or not item_ids:
        return 0

    conn = get_connection(db_path)
    cur = conn.cursor()

    if config_dir is not None:
        if fields.get("artist_id"):
            _ensure_entity_in_db(cur, "artist_id", fields["artist_id"], config_dir)
        if fields.get("provider_id"):
            _ensure_entity_in_db(cur, "provider_id", fields["provider_id"], config_dir)

    set_clause = ", ".join(f"{k} = ?" for k in fields) + ", manual_override = 1"
    placeholders = ",".join("?" for _ in item_ids)
    cur.execute(
        f"UPDATE media_items SET {set_clause} WHERE id IN ({placeholders})",
        (*fields.values(), *item_ids),
    )
    updated = cur.rowcount
    conn.commit()
    conn.close()
    return updated


def clear_manual_override(item_ids: list[int], db_path: Path | None = None) -> int:
    """Hebt die manuelle Sperre wieder auf - der nächste 'resolve'-Lauf berechnet Artist/Provider/
    Collection für diese Items wieder automatisch aus den Ordnernamen."""
    if not item_ids:
        return 0
    placeholders = ",".join("?" for _ in item_ids)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(f"UPDATE media_items SET manual_override = 0 WHERE id IN ({placeholders})", tuple(item_ids))
    updated = cur.rowcount
    conn.commit()
    conn.close()
    return updated


def save_title_overrides(values: dict[int, str], db_path: Path | None = None) -> int:
    """values: {item_id: neuer_titel}. Leerer String löscht den Override wieder (Fallback auf den
    Dateinamen-Stem beim naming-Schritt)."""
    if not values:
        return 0
    conn = get_connection(db_path)
    cur = conn.cursor()
    updated = 0
    for item_id, title in values.items():
        cur.execute(
            "UPDATE media_items SET title_override = ? WHERE id = ?",
            (title.strip() or None, item_id),
        )
        updated += cur.rowcount
    conn.commit()
    conn.close()
    return updated
