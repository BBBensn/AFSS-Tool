from pathlib import Path

from afss.db import get_connection


def _where_profile(profile_id: str | None) -> tuple[str, tuple]:
    if profile_id:
        return "WHERE profile_id = ?", (profile_id,)
    return "", ()


def report_overview(profile_id: str | None = None, db_path: Path | None = None) -> list[dict]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    clause, params = _where_profile(profile_id)

    cur.execute(f"SELECT DISTINCT profile_id FROM media_items {clause}", params)
    profile_ids = [r[0] for r in cur.fetchall()]

    results = []
    for pid in profile_ids:
        cur.execute("SELECT COUNT(*) FROM media_items WHERE profile_id = ?", (pid,))
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM media_items WHERE profile_id = ? AND artist_id IS NOT NULL", (pid,)
        )
        resolved = cur.fetchone()[0]
        cur.execute(
            "SELECT media_type, COUNT(*) FROM media_items WHERE profile_id = ? GROUP BY media_type", (pid,)
        )
        by_type = dict(cur.fetchall())
        results.append(
            {
                "profile_id": pid,
                "total": total,
                "resolved": resolved,
                "unresolved": total - resolved,
                "media_type_counts": by_type,
            }
        )

    conn.close()
    return results


def report_missing(profile_id: str | None = None, db_path: Path | None = None) -> list[tuple]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    clause, params = _where_profile(profile_id)
    extra = "AND artist_id IS NULL" if clause else "WHERE artist_id IS NULL"
    cur.execute(
        f"SELECT profile_id, rel_path, folder_level1, folder_level2 FROM media_items {clause} {extra}",
        params,
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def report_needs_review(profile_id: str | None = None, db_path: Path | None = None) -> list[tuple]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    clause, params = _where_profile(profile_id)
    extra = "AND needs_review = 1" if clause else "WHERE needs_review = 1"
    cur.execute(
        f"SELECT profile_id, rel_path, review_reason FROM media_items {clause} {extra}",
        params,
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def report_dedupe(profile_id: str | None = None, db_path: Path | None = None) -> list[tuple]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    if profile_id:
        cur.execute(
            """
            SELECT g.file_hash, COUNT(m.id), g.kept_media_item_id
            FROM dedupe_groups g
            JOIN dedupe_group_members gm ON gm.dedupe_group_id = g.id
            JOIN media_items m ON m.id = gm.media_item_id
            WHERE m.profile_id = ? AND gm.action = 'pending'
            GROUP BY g.id
            """,
            (profile_id,),
        )
    else:
        cur.execute(
            """
            SELECT g.file_hash, COUNT(gm.media_item_id), g.kept_media_item_id
            FROM dedupe_groups g
            JOIN dedupe_group_members gm ON gm.dedupe_group_id = g.id
            WHERE gm.action = 'pending'
            GROUP BY g.id
            """
        )
    rows = cur.fetchall()
    conn.close()
    return rows
