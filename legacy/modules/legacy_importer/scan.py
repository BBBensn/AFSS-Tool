from pathlib import Path
import os
import sqlite3
import json
import datetime
from typing import Optional

from core.config import load_legacy_profiles


def _map_media_type(suffix: str) -> Optional[str]:
    s = suffix.lower()
    if s == ".mp4":
        return "video"
    if s in {".jpg", ".jpeg", ".png"}:
        return "photo"
    if s == ".json":
        return "provider_meta"
    if s == ".txt":
        return "note"
    return "unknown"


def scan_profile(profile_id: str, config_dir: Path, db_path: Path) -> dict:
    """Scan the legacy root defined in legacy_profiles and insert media items into DB.

    Returns a simple counts dict: {media_type: count, ...}
    """
    cfg_path = Path(config_dir) / "legacy_profiles.yml"
    data = load_legacy_profiles(cfg_path)
    profiles = data.get("profiles", []) if isinstance(data, dict) else []

    profile = None
    for p in profiles:
        if p.get("id") == profile_id:
            profile = p
            break

    if profile is None:
        raise ValueError(f"Profile not found: {profile_id}")

    root_raw = profile.get("root_path")
    if not root_raw:
        raise ValueError(f"Profile {profile_id} has no root_path")

    root = Path(root_raw)
    if not root.exists() or not root.is_dir():
        print(f"[WARN] Root path does not exist or is not a directory: {root}")
        return {}

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    counts = {}

    now_iso = datetime.datetime.now().isoformat()

    # Walk
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            file_path = Path(dirpath) / fn
            suffix = file_path.suffix.lower()
            media_type = _map_media_type(suffix)
            # skip certain hidden/temp files
            if fn.startswith('.'):
                continue

            rel = file_path.relative_to(root)
            rel_str = rel.as_posix()

            # artist folder is first-part under root, if present
            parts = rel.parts
            artist_folder = parts[0] if len(parts) >= 2 else None

            # fs timestamps
            try:
                st = file_path.stat()
                fs_created = datetime.datetime.fromtimestamp(st.st_ctime).isoformat()
                fs_modified = datetime.datetime.fromtimestamp(st.st_mtime).isoformat()
            except Exception:
                fs_created = None
                fs_modified = None

            cur.execute(
                """
                INSERT INTO media_items(
                    path, media_type, artist_id, provider_id, collection_name,
                    legacy_profile_id, origin_hint, fs_created_at, fs_modified_at, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(file_path),
                    media_type,
                    None,
                    None,
                    None,
                    profile_id,
                    rel_str,
                    fs_created,
                    fs_modified,
                    now_iso,
                ),
            )

            counts[media_type] = counts.get(media_type, 0) + 1

    conn.commit()
    conn.close()

    return counts
