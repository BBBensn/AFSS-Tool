import datetime
import os
from collections import Counter
from pathlib import Path

from afss.config import get_profile
from afss.db import get_connection
from afss.normalize import normalize_name
from afss.tagging import get_trash_folder_names

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".m4v"}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
NOTE_EXTS = {".txt", ".md"}
PROVIDER_META_EXTS = {".json"}


def classify_media_type(ext: str) -> str:
    ext = ext.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in PHOTO_EXTS:
        return "photo"
    if ext in NOTE_EXTS:
        return "note"
    if ext in PROVIDER_META_EXTS:
        return "provider_meta"
    return "unknown"


def scan_profile(profile_id: str, config_dir: Path, db_path: Path | None = None) -> dict:
    profile = get_profile(config_dir, profile_id)
    root = Path(profile["root_path"]).expanduser()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"root_path existiert nicht oder ist kein Verzeichnis: {root}")

    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO profiles(id, description, root_path, disk_label, enabled, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            description=excluded.description,
            root_path=excluded.root_path,
            disk_label=excluded.disk_label,
            enabled=excluded.enabled
        """,
        (
            profile_id,
            profile.get("description"),
            str(root),
            profile.get("disk_label"),
            1 if profile.get("enabled", True) else 0,
            datetime.datetime.now().isoformat(),
        ),
    )

    cur.execute("DELETE FROM media_items WHERE profile_id = ?", (profile_id,))

    trash_names = get_trash_folder_names(db_path)

    now_iso = datetime.datetime.now().isoformat()
    media_type_counts = Counter()
    rows = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if not d.startswith(".") and normalize_name(d) not in trash_names
        ]

        for fn in filenames:
            if fn.startswith("."):
                continue
            file_path = Path(dirpath) / fn
            rel = file_path.relative_to(root)
            parts = rel.parts

            ext = file_path.suffix.lower()
            media_type = classify_media_type(ext)

            folder_level1 = parts[0] if len(parts) > 1 else None
            folder_level2 = parts[1] if len(parts) > 2 else None

            try:
                st = file_path.stat()
                size_bytes = st.st_size
                fs_created_at = datetime.datetime.fromtimestamp(st.st_ctime).isoformat()
                fs_modified_at = datetime.datetime.fromtimestamp(st.st_mtime).isoformat()
            except OSError:
                size_bytes = None
                fs_created_at = None
                fs_modified_at = None

            rows.append(
                (
                    profile_id, str(file_path), rel.as_posix(), fn, ext, media_type,
                    size_bytes, fs_created_at, fs_modified_at,
                    folder_level1, folder_level2, now_iso,
                )
            )
            media_type_counts[media_type] += 1

    cur.executemany(
        """
        INSERT INTO media_items(
            profile_id, path, rel_path, filename, ext, media_type,
            size_bytes, fs_created_at, fs_modified_at,
            folder_level1, folder_level2, scanned_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    cur.execute("SELECT alias FROM artist_aliases")
    known_aliases = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT alias FROM provider_aliases")
    known_aliases |= {r[0] for r in cur.fetchall()}

    unknown_level1 = set()
    unknown_level2 = set()
    for row in rows:
        folder_level1, folder_level2 = row[9], row[10]
        if folder_level1 and normalize_name(folder_level1) not in known_aliases:
            unknown_level1.add(folder_level1)
        if folder_level2 and normalize_name(folder_level2) not in known_aliases:
            unknown_level2.add(folder_level2)

    conn.commit()
    conn.close()

    return {
        "profile_id": profile_id,
        "root": str(root),
        "total_files": len(rows),
        "media_type_counts": dict(media_type_counts),
        "unknown_folder_level1_count": len(unknown_level1),
        "unknown_folder_level2_count": len(unknown_level2),
    }
