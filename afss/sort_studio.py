from pathlib import Path

from afss.db import get_connection
from afss.tagging import get_json_canonical_name

_ALLOWED_BULK_FIELDS = {"artist_id", "provider_id", "collection_name"}
_TABLE_BY_FIELD = {"artist_id": ("artists", "artist"), "provider_id": ("providers", "provider")}
_ALLOWED_ITEM_STATUS = {"active", "trash", "extra"}


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
    manuelle Sortier-Studio-Ansicht. profile_id='all' liefert profilübergreifend alle Profile auf
    einmal (gleiche Konvention wie dedupe_profile/apply_dedupe) - wichtig für Artists, die über
    mehrere Platten verteilt sind und sich nur so vollständig zusammenführen lassen. Dateien, die
    bereits als Duplikat zum Löschen/Behalten markiert wurden (dedupe_group_members.action in
    pending/delete), werden ausgeblendet - die sind nicht Teil dessen, was der Nutzer noch manuell
    einsortieren muss."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    where_clause = "dgm.media_item_id IS NULL" if profile_id == "all" else "m.profile_id = ? AND dgm.media_item_id IS NULL"
    params = () if profile_id == "all" else (profile_id,)
    cur.execute(
        f"""
        SELECT m.id, m.filename, m.rel_path, m.media_type, m.artist_id, a.canonical_name,
               m.provider_id, p.canonical_name, m.collection_name, m.title_override, m.manual_override,
               m.item_status, m.tags, m.profile_id
        FROM media_items m
        LEFT JOIN artists a ON a.id = m.artist_id
        LEFT JOIN providers p ON p.id = m.provider_id
        LEFT JOIN dedupe_group_members dgm ON dgm.media_item_id = m.id AND dgm.action IN ('pending', 'delete')
        WHERE {where_clause}
        ORDER BY a.canonical_name IS NULL, a.canonical_name, m.collection_name IS NULL, m.collection_name, m.filename
        """,
        params,
    )
    rows = cur.fetchall()

    item_ids = [r[0] for r in rows]
    co_artists_by_item: dict[int, list[dict]] = {}
    if item_ids:
        placeholders = ",".join("?" for _ in item_ids)
        cur.execute(
            f"""
            SELECT mca.media_item_id, a.id, a.canonical_name
            FROM media_item_co_artists mca
            JOIN artists a ON a.id = mca.artist_id
            WHERE mca.media_item_id IN ({placeholders})
            ORDER BY a.canonical_name
            """,
            item_ids,
        )
        for item_id, co_artist_id, name in cur.fetchall():
            co_artists_by_item.setdefault(item_id, []).append({"id": co_artist_id, "name": name})

    conn.close()

    artists: dict[str, dict] = {}
    for (
        item_id, filename, rel_path, media_type, artist_id, artist_name,
        provider_id, provider_name, collection_name, title_override, manual_override,
        item_status, tags, item_profile_id,
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
                "profile_id": item_profile_id,
                "item_status": item_status or "active",
                "tags": tags or "",
                "co_artists": co_artists_by_item.get(item_id, []),
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


def save_tags(values: dict[int, str], db_path: Path | None = None) -> int:
    """values: {item_id: neue_tags_als_kommaliste}. Ersetzt die Tags der jeweiligen Datei komplett
    (im Gegensatz zu add_tags, das für Bulk-Ergänzung gedacht ist)."""
    if not values:
        return 0
    conn = get_connection(db_path)
    cur = conn.cursor()
    updated = 0
    for item_id, tags in values.items():
        cur.execute("UPDATE media_items SET tags = ? WHERE id = ?", (tags.strip() or None, item_id))
        updated += cur.rowcount
    conn.commit()
    conn.close()
    return updated


def add_tags(item_ids: list[int], new_tags: list[str], db_path: Path | None = None) -> int:
    """Ergänzt die gegebenen Tags bei mehreren Dateien auf einmal, ohne bereits vorhandene
    individuelle Tags zu überschreiben (dedupliziert pro Datei)."""
    new_tags = [t.strip() for t in new_tags if t.strip()]
    if not new_tags or not item_ids:
        return 0
    conn = get_connection(db_path)
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in item_ids)
    cur.execute(f"SELECT id, tags FROM media_items WHERE id IN ({placeholders})", item_ids)
    rows = cur.fetchall()
    updated = 0
    for item_id, existing_tags in rows:
        current = [t.strip() for t in (existing_tags or "").split(",") if t.strip()]
        for tag in new_tags:
            if tag not in current:
                current.append(tag)
        cur.execute("UPDATE media_items SET tags = ? WHERE id = ?", (", ".join(current), item_id))
        updated += 1
    conn.commit()
    conn.close()
    return updated


def set_item_status(item_ids: list[int], status: str, db_path: Path | None = None) -> int:
    """Markiert Dateien als 'trash' (wird von plan/apply automatisch ausgeschlossen), 'extra'
    (z.B. Behind-the-Scenes-Fotos, die man behalten aber nicht wie normale Clips einsortieren
    will) oder 'active' (Standard, zurücksetzen). Löscht nichts - reines Ausschluss-Flag,
    tatsächliches Löschen bleibt ein separater, expliziter Schritt."""
    if status not in _ALLOWED_ITEM_STATUS or not item_ids:
        return 0
    placeholders = ",".join("?" for _ in item_ids)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(f"UPDATE media_items SET item_status = ? WHERE id IN ({placeholders})", (status, *item_ids))
    updated = cur.rowcount
    conn.commit()
    conn.close()
    return updated


def add_co_artist(
    item_ids: list[int], artist_id: str, db_path: Path | None = None, config_dir: Path | None = None
) -> int:
    """Verknüpft mehrere Dateien zusätzlich mit einem weiteren Artist (Coop/Feature), ohne den
    Hauptartist (artist_id) zu ändern - der bestimmt weiterhin den Zielordner bei apply."""
    if not artist_id or not item_ids:
        return 0
    conn = get_connection(db_path)
    cur = conn.cursor()
    if config_dir is not None:
        _ensure_entity_in_db(cur, "artist_id", artist_id, config_dir)
    added = 0
    for item_id in item_ids:
        cur.execute(
            "INSERT OR IGNORE INTO media_item_co_artists(media_item_id, artist_id) VALUES (?, ?)",
            (item_id, artist_id),
        )
        added += cur.rowcount
    conn.commit()
    conn.close()
    return added


def remove_co_artist(item_id: int, artist_id: str, db_path: Path | None = None) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM media_item_co_artists WHERE media_item_id = ? AND artist_id = ?", (item_id, artist_id)
    )
    removed = cur.rowcount
    conn.commit()
    conn.close()
    return removed
