from pathlib import Path

from afss.db import get_connection
from afss.normalize import normalize_name


def resolve_profile(profile_id: str, db_path: Path | None = None) -> dict:
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, folder_level1, folder_level2 FROM media_items WHERE profile_id = ?",
        (profile_id,),
    )
    items = cur.fetchall()

    cur.execute("SELECT alias, artist_id FROM artist_aliases")
    artist_by_alias = dict(cur.fetchall())
    cur.execute("SELECT alias, provider_id FROM provider_aliases")
    provider_by_alias = dict(cur.fetchall())

    resolved_count = 0
    unresolved = {}  # (folder_name, level) -> {"count": int, "sample_path": str}

    for item_id, folder_level1, folder_level2 in items:
        norm1 = normalize_name(folder_level1) if folder_level1 else None
        norm2 = normalize_name(folder_level2) if folder_level2 else None

        level1_is_artist = norm1 is not None and norm1 in artist_by_alias
        level1_is_provider = norm1 is not None and norm1 in provider_by_alias
        level2_is_artist = norm2 is not None and norm2 in artist_by_alias
        level2_is_provider = norm2 is not None and norm2 in provider_by_alias

        # Manche Platten sind artist-first (level1=Artist), manche category-first
        # (level1=Kategorie, level2=Artist) - daher beide Ebenen für beide Rollen probieren.
        # level1 hat Vorrang für Artist, level2 für Provider (üblichere Reihenfolge).
        if level1_is_artist:
            artist_id = artist_by_alias[norm1]
        elif level2_is_artist:
            artist_id = artist_by_alias[norm2]
        else:
            artist_id = None

        if level2_is_provider:
            provider_id = provider_by_alias[norm2]
        elif level1_is_provider:
            provider_id = provider_by_alias[norm1]
        else:
            provider_id = None

        collection_name = folder_level2 if (folder_level2 and not level2_is_artist and not level2_is_provider) else None

        cur.execute(
            "UPDATE media_items SET artist_id = ?, provider_id = ?, collection_name = ? WHERE id = ?",
            (artist_id, provider_id, collection_name, item_id),
        )

        if artist_id:
            resolved_count += 1

        if folder_level1 and not level1_is_artist and not level1_is_provider:
            key = (folder_level1, 1)
            entry = unresolved.setdefault(key, {"count": 0, "sample_path": folder_level1})
            entry["count"] += 1

        if folder_level2 and not level2_is_artist and not level2_is_provider:
            key = (folder_level2, 2)
            entry = unresolved.setdefault(key, {"count": 0, "sample_path": folder_level2})
            entry["count"] += 1

    for (folder_name, level), info in unresolved.items():
        cur.execute(
            """
            INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, sample_path, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(profile_id, folder_name, folder_level) DO UPDATE SET
                occurrence_count=excluded.occurrence_count,
                sample_path=excluded.sample_path
            """,
            (profile_id, folder_name, level, info["count"], info["sample_path"]),
        )

    conn.commit()

    cur.execute(
        """
        SELECT folder_name, folder_level, occurrence_count FROM unresolved_folders
        WHERE profile_id = ? AND status = 'pending'
        ORDER BY occurrence_count DESC LIMIT 10
        """,
        (profile_id,),
    )
    top_unresolved = cur.fetchall()
    conn.close()

    total = len(items)
    return {
        "profile_id": profile_id,
        "total": total,
        "resolved": resolved_count,
        "unresolved": total - resolved_count,
        "top_unresolved": top_unresolved,
    }
