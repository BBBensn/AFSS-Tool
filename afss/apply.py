import datetime
import hashlib
import shutil
from pathlib import Path

from afss.db import get_connection


def _sanitize_folder_name(name: str) -> str:
    return name.replace("/", "-").replace("\x00", "").strip()


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def apply_profile(profile_id: str, target_dir: Path, db_path: Path | None = None) -> dict:
    """Kopiert alle 'ready' Items (needs_review=0, planned_filename gesetzt, noch nicht verified)
    nach target_dir/<artist>/<planned_filename> und verifiziert per Hash-Vergleich."""
    target_dir = Path(target_dir)
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT m.id, m.path, m.planned_filename, a.canonical_name, m.collection_name
        FROM media_items m
        LEFT JOIN artists a ON a.id = m.artist_id
        WHERE m.profile_id = ? AND m.needs_review = 0 AND m.planned_filename IS NOT NULL AND m.verified = 0
        """,
        (profile_id,),
    )
    rows = cur.fetchall()

    now_iso = datetime.datetime.now().isoformat()
    copied = 0
    verified = 0
    skipped_existing = 0
    failed = []

    for item_id, source_path, planned_filename, artist_name, collection_name in rows:
        source = Path(source_path)
        if not source.exists():
            failed.append({"item_id": item_id, "reason": f"Quelle fehlt: {source}"})
            continue

        dest_dir = target_dir / (artist_name or "_unresolved")
        if collection_name:
            dest_dir = dest_dir / _sanitize_folder_name(collection_name)
        dest_path = dest_dir / planned_filename

        if dest_path.exists():
            skipped_existing += 1
            if _sha256(source) == _sha256(dest_path):
                cur.execute(
                    "UPDATE media_items SET target_path = ?, applied_at = ?, verified = 1 WHERE id = ?",
                    (str(dest_path), now_iso, item_id),
                )
                verified += 1
            else:
                failed.append(
                    {"item_id": item_id, "reason": f"Ziel existiert bereits mit anderem Inhalt: {dest_path}"}
                )
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest_path)
        copied += 1

        if _sha256(source) == _sha256(dest_path):
            cur.execute(
                "UPDATE media_items SET target_path = ?, applied_at = ?, verified = 1 WHERE id = ?",
                (str(dest_path), now_iso, item_id),
            )
            verified += 1
        else:
            cur.execute(
                "UPDATE media_items SET target_path = ?, applied_at = ?, verified = 0 WHERE id = ?",
                (str(dest_path), now_iso, item_id),
            )
            failed.append({"item_id": item_id, "reason": "Hash-Mismatch nach Kopie"})

    conn.commit()
    conn.close()

    return {
        "profile_id": profile_id,
        "candidates": len(rows),
        "copied": copied,
        "verified": verified,
        "skipped_existing": skipped_existing,
        "failed": failed,
    }


def delete_verified_sources(profile_id: str, db_path: Path | None = None) -> dict:
    """Löscht Quelldateien nur, wenn verified=1 UND die Zieldatei tatsächlich existiert."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, path, target_path FROM media_items WHERE profile_id = ? AND verified = 1 AND target_path IS NOT NULL",
        (profile_id,),
    )
    rows = cur.fetchall()
    conn.close()

    deleted = 0
    missing_source = 0
    skipped_missing_target = 0

    for _item_id, source_path, target_path in rows:
        source = Path(source_path)
        target = Path(target_path)
        if not target.exists():
            skipped_missing_target += 1
            continue
        if source.exists():
            source.unlink()
            deleted += 1
        else:
            missing_source += 1

    return {"deleted": deleted, "missing_source": missing_source, "skipped_missing_target": skipped_missing_target}
