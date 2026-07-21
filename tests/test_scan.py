from pathlib import Path

import yaml

from afss.db import get_connection, init_schema
from afss.scan import scan_profile


def _write_profiles_yml(config_dir: Path, profile_id: str, root: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "profiles": [
            {
                "id": profile_id,
                "description": "test profile",
                "root_path": str(root),
                "enabled": True,
            }
        ]
    }
    (config_dir / "legacy_profiles.yml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _build_fake_root(root: Path) -> None:
    (root / "Artist One" / "Collection A").mkdir(parents=True)
    (root / "Artist One" / "Collection A" / "video1.mp4").write_bytes(b"x")
    (root / "Artist One" / "Collection A" / "photo1.jpg").write_bytes(b"x")
    (root / "Artist One" / "ProviderX").mkdir(parents=True)
    (root / "Artist One" / "ProviderX" / "meta.json").write_text("{}", encoding="utf-8")
    (root / "Artist Two").mkdir(parents=True)
    (root / "Artist Two" / "video2.mp4").write_bytes(b"x")


def test_scan_counts_and_folder_levels(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 4
    assert result["media_type_counts"]["video"] == 2
    assert result["media_type_counts"]["photo"] == 1
    assert result["media_type_counts"]["provider_meta"] == 1

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT folder_level1, folder_level2 FROM media_items WHERE filename = 'video1.mp4'")
    row = cur.fetchone()
    conn.close()
    assert row == ("Artist One", "Collection A")


def test_scan_is_idempotent(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    result = scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE profile_id = 'test_profile'")
    count = cur.fetchone()[0]
    conn.close()

    assert count == result["total_files"] == 4
