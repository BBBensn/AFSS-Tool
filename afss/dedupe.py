import datetime
import hashlib
from collections import defaultdict
from pathlib import Path

from afss.db import get_connection


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _resolution_score(artist_id, provider_id) -> int:
    return (1 if artist_id else 0) + (1 if provider_id else 0)


def _pick_kept(members: list[tuple]) -> int:
    """members: (item_id, path, artist_id, provider_id, fs_created_at). Bestaufgelöster Pfad gewinnt, sonst ältester."""

    def sort_key(m):
        item_id, _path, artist_id, provider_id, fs_created_at = m
        return (-_resolution_score(artist_id, provider_id), fs_created_at or "")

    return min(members, key=sort_key)[0]


def dedupe_profile(profile_id: str, db_path: Path | None = None) -> dict:
    conn = get_connection(db_path)
    cur = conn.cursor()

    if profile_id and profile_id != "all":
        cur.execute(
            "SELECT id, path, size_bytes, artist_id, provider_id, fs_created_at FROM media_items WHERE profile_id = ?",
            (profile_id,),
        )
    else:
        cur.execute("SELECT id, path, size_bytes, artist_id, provider_id, fs_created_at FROM media_items")
    rows = cur.fetchall()

    by_size = defaultdict(list)
    for row in rows:
        if row[2] is None:
            continue
        by_size[row[2]].append(row)

    now_iso = datetime.datetime.now().isoformat()
    groups_created = 0
    duplicate_files = 0
    hashed_count = 0

    for size_bytes, candidates in by_size.items():
        if len(candidates) < 2:
            continue

        by_hash = defaultdict(list)
        for item_id, path, _size, artist_id, provider_id, fs_created_at in candidates:
            file_path = Path(path)
            if not file_path.exists():
                continue
            file_hash = _sha256(file_path)
            hashed_count += 1
            cur.execute("UPDATE media_items SET file_hash = ? WHERE id = ?", (file_hash, item_id))
            by_hash[file_hash].append((item_id, path, artist_id, provider_id, fs_created_at))

        for file_hash, members in by_hash.items():
            if len(members) < 2:
                continue

            member_ids = {m[0] for m in members}
            computed_kept_id = _pick_kept(members)

            cur.execute("SELECT id, kept_media_item_id FROM dedupe_groups WHERE file_hash = ?", (file_hash,))
            existing = cur.fetchone()

            if existing:
                group_id, existing_kept_id = existing
                kept_id = existing_kept_id if existing_kept_id is not None else computed_kept_id
            else:
                cur.execute(
                    "INSERT INTO dedupe_groups(file_hash, kept_media_item_id, created_at) VALUES (?, ?, ?)",
                    (file_hash, computed_kept_id, now_iso),
                )
                group_id = cur.lastrowid
                kept_id = computed_kept_id
                groups_created += 1

            cur.execute("SELECT media_item_id FROM dedupe_group_members WHERE dedupe_group_id = ?", (group_id,))
            already_present = {r[0] for r in cur.fetchall()}

            for item_id in member_ids - already_present:
                action = "keep" if item_id == kept_id else "pending"
                cur.execute(
                    "INSERT INTO dedupe_group_members(dedupe_group_id, media_item_id, action) VALUES (?, ?, ?)",
                    (group_id, item_id, action),
                )
                if item_id != kept_id:
                    duplicate_files += 1

    conn.commit()
    conn.close()

    return {"hashed_count": hashed_count, "groups": groups_created, "duplicate_files": duplicate_files}


def apply_dedupe(profile_id: str, db_path: Path | None = None) -> dict:
    conn = get_connection(db_path)
    cur = conn.cursor()

    if profile_id and profile_id != "all":
        cur.execute(
            """
            SELECT gm.rowid, m.path FROM dedupe_group_members gm
            JOIN media_items m ON m.id = gm.media_item_id
            WHERE gm.action = 'pending' AND m.profile_id = ?
            """,
            (profile_id,),
        )
    else:
        cur.execute(
            """
            SELECT gm.rowid, m.path FROM dedupe_group_members gm
            JOIN media_items m ON m.id = gm.media_item_id
            WHERE gm.action = 'pending'
            """
        )
    rows = cur.fetchall()

    deleted = 0
    missing = 0
    for member_rowid, path in rows:
        file_path = Path(path)
        if file_path.exists():
            file_path.unlink()
            deleted += 1
        else:
            missing += 1
        cur.execute("UPDATE dedupe_group_members SET action = 'delete' WHERE rowid = ?", (member_rowid,))

    conn.commit()
    conn.close()
    return {"deleted": deleted, "missing": missing}
