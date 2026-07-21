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
        artist_id = artist_by_alias.get(normalize_name(folder_level1)) if folder_level1 else None
        provider_id = provider_by_alias.get(normalize_name(folder_level2)) if folder_level2 else None
        collection_name = folder_level2 if (folder_level2 and provider_id is None) else None

        cur.execute(
            "UPDATE media_items SET artist_id = ?, provider_id = ?, collection_name = ? WHERE id = ?",
            (artist_id, provider_id, collection_name, item_id),
        )

        if artist_id:
            resolved_count += 1
        elif folder_level1:
            key = (folder_level1, 1)
            entry = unresolved.setdefault(key, {"count": 0, "sample_path": folder_level1})
            entry["count"] += 1

        if folder_level2 and provider_id is None:
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
