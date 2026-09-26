from pathlib import Path

import yaml

from afss.db import get_connection, init_schema
from afss.scan import scan_profile
from afss.tagging import set_trash


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


def test_scan_skips_hidden_directories(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    (root / ".Spotlight-V100").mkdir(parents=True)
    (root / ".Spotlight-V100" / "index.dat").write_bytes(b"x")
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 4


def test_scan_skips_folders_marked_as_trash(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    (root / "$RECYCLE.BIN").mkdir(parents=True)
    (root / "$RECYCLE.BIN" / "deleted.mp4").write_bytes(b"x")
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('test_profile', '$RECYCLE.BIN', 1, 1, 'pending')"
    )
    unresolved_id = cur.lastrowid
    conn.commit()
    conn.close()
    set_trash(unresolved_id, db_path)

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 4


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


def test_rescan_preserves_manual_tagging_and_id(tmp_path):
    """Regression: scan() loeschte frueher bei JEDEM Lauf alle media_items des Profils und baute sie
    komplett neu auf (auch fuer Dateien, die sich gar nicht geaendert haben) - das hat jegliche im
    Sortier-Studio gesetzte Zuordnung (Artist, Tags, manual_override, ...) bei einem simplen Rescan
    wieder geloescht. Ein Rescan darf bestehende, unveraenderte Dateien nur in ihren dateisystem-
    abgeleiteten Spalten auffrischen, niemals in ihren Tagging-Spalten."""
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO artists(id, canonical_name) VALUES ('artist_one', 'Artist One')"
    )
    cur.execute(
        "UPDATE media_items SET artist_id = 'artist_one', tags = 'favorite', manual_override = 1, "
        "title_override = 'Custom Title' WHERE filename = 'video1.mp4'"
    )
    cur.execute("SELECT id FROM media_items WHERE filename = 'video1.mp4'")
    original_id = cur.fetchone()[0]
    conn.commit()
    conn.close()

    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, artist_id, tags, manual_override, title_override FROM media_items WHERE filename = 'video1.mp4'"
    )
    row = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE profile_id = 'test_profile'")
    total = cur.fetchone()[0]
    conn.close()

    assert row == (original_id, "artist_one", "favorite", 1, "Custom Title")
    assert total == 4  # keine Dublette angelegt


def test_scan_marks_removed_files_as_missing_without_deleting(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    (root / "Artist Two" / "video2.mp4").unlink()

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 3  # nur noch auf der Platte vorhandene Dateien
    assert result["newly_missing"] == 1
    assert result["missing_total"] == 1

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE profile_id = 'test_profile'")
    total = cur.fetchone()[0]
    cur.execute("SELECT missing_since FROM media_items WHERE filename = 'video2.mp4'")
    missing_since = cur.fetchone()[0]
    cur.execute("SELECT missing_since FROM media_items WHERE filename = 'video1.mp4'")
    still_present = cur.fetchone()[0]
    conn.close()

    assert total == 4  # Zeile bleibt erhalten, wird nicht geloescht
    assert missing_since is not None
    assert still_present is None


def test_scan_clears_missing_since_when_file_reappears(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    video_path = root / "Artist Two" / "video2.mp4"
    video_path.unlink()
    scan_profile("test_profile", config_dir, db_path)
    video_path.write_bytes(b"x")

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["missing_total"] == 0
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT missing_since FROM media_items WHERE filename = 'video2.mp4'")
    missing_since = cur.fetchone()[0]
    conn.close()
    assert missing_since is None


def test_scan_does_not_advance_missing_since_on_repeated_scans(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    (root / "Artist Two" / "video2.mp4").unlink()
    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE media_items SET missing_since = '2020-01-01T00:00:00' WHERE filename = 'video2.mp4'")
    conn.commit()
    conn.close()

    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT missing_since FROM media_items WHERE filename = 'video2.mp4'")
    missing_since = cur.fetchone()[0]
    conn.close()
    assert missing_since == "2020-01-01T00:00:00"


def test_scan_new_file_added_alongside_existing_tagged_files(tmp_path):
    """Der eigentliche Anlassfall: neue Clips kommen dazu, der Rest ist schon getaggt - ein Rescan
    darf nur die neue Datei ergaenzen, den Rest unangetastet lassen."""
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO artists(id, canonical_name) VALUES ('artist_one', 'Artist One')")
    cur.execute("UPDATE media_items SET artist_id = 'artist_one', manual_override = 1 WHERE filename = 'video1.mp4'")
    conn.commit()
    conn.close()

    (root / "Artist Three").mkdir(parents=True)
    (root / "Artist Three" / "new_clip.mp4").write_bytes(b"x")

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 5
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id, manual_override FROM media_items WHERE filename = 'video1.mp4'")
    preserved = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE filename = 'new_clip.mp4'")
    new_count = cur.fetchone()[0]
    conn.close()
    assert preserved == ("artist_one", 1)
    assert new_count == 1
