import json
from pathlib import Path

import yaml

from afss.db import get_connection, init_schema
from afss.migrate_legacy import migrate_legacy_json
from afss.resolve import resolve_profile
from afss.scan import scan_profile


def _setup(tmp_path):
    root = tmp_path / "fake_root"
    (root / "Artist One" / "Collection A").mkdir(parents=True)
    (root / "Artist One" / "Collection A" / "video1.mp4").write_bytes(b"x")
    (root / "Artist One" / "ProviderX").mkdir(parents=True)
    (root / "Artist One" / "ProviderX" / "meta.json").write_text("{}", encoding="utf-8")
    (root / "UnknownArtist").mkdir(parents=True)
    (root / "UnknownArtist" / "video2.mp4").write_bytes(b"x")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "legacy_profiles.yml").write_text(
        yaml.safe_dump({"profiles": [{"id": "test_profile", "root_path": str(root), "enabled": True}]}),
        encoding="utf-8",
    )
    (config_dir / "artists.json").write_text(
        json.dumps({"artists": [{"id": "artist_1", "canonical_name": "Artist One", "aliases": []}]}),
        encoding="utf-8",
    )
    (config_dir / "providers.json").write_text(
        json.dumps({"providers": [{"id": "provider_x", "canonical_name": "ProviderX", "aliases": []}]}),
        encoding="utf-8",
    )

    db_path = tmp_path / "test.db"
    init_schema(db_path)
    migrate_legacy_json(config_dir, db_path)
    scan_profile("test_profile", config_dir, db_path)
    return config_dir, db_path


def test_resolve_matches_known_aliases_and_flags_unknown(tmp_path):
    _setup(tmp_path)
    db_path = tmp_path / "test.db"

    result = resolve_profile("test_profile", db_path)

    assert result["total"] == 3
    assert result["resolved"] == 2
    assert result["unresolved"] == 1

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id, provider_id FROM media_items WHERE filename = 'meta.json'")
    assert cur.fetchone() == ("artist_1", "provider_x")
    cur.execute("SELECT artist_id FROM media_items WHERE filename = 'video2.mp4'")
    assert cur.fetchone() == (None,)
    cur.execute("SELECT occurrence_count, status FROM unresolved_folders WHERE folder_name = 'UnknownArtist'")
    assert cur.fetchone() == (1, "pending")
    conn.close()


def test_resolve_falls_back_to_level2_for_category_first_drives(tmp_path):
    """Manche Platten sind category-first (level1=Kategorie, level2=Artist) statt artist-first."""
    root = tmp_path / "fake_root"
    (root / "_Category" / "Artist Two").mkdir(parents=True)
    (root / "_Category" / "Artist Two" / "clip.mp4").write_bytes(b"x")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "legacy_profiles.yml").write_text(
        yaml.safe_dump({"profiles": [{"id": "cat_profile", "root_path": str(root), "enabled": True}]}),
        encoding="utf-8",
    )
    (config_dir / "artists.json").write_text(
        json.dumps({"artists": [{"id": "artist_2", "canonical_name": "Artist Two", "aliases": []}]}),
        encoding="utf-8",
    )
    (config_dir / "providers.json").write_text(json.dumps({"providers": []}), encoding="utf-8")

    db_path = tmp_path / "test.db"
    init_schema(db_path)
    migrate_legacy_json(config_dir, db_path)
    scan_profile("cat_profile", config_dir, db_path)

    result = resolve_profile("cat_profile", db_path)

    assert result["resolved"] == 1

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id, collection_name FROM media_items WHERE filename = 'clip.mp4'")
    assert cur.fetchone() == ("artist_2", None)
    cur.execute("SELECT status FROM unresolved_folders WHERE folder_name = '_Category'")
    assert cur.fetchone() == ("pending",)
    cur.execute("SELECT COUNT(*) FROM unresolved_folders WHERE folder_name = 'Artist Two'")
    assert cur.fetchone()[0] == 0
    conn.close()


def test_resolve_is_idempotent_and_preserves_manual_status(tmp_path):
    _setup(tmp_path)
    db_path = tmp_path / "test.db"
    resolve_profile("test_profile", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE unresolved_folders SET status = 'ignored' WHERE folder_name = 'UnknownArtist'")
    conn.commit()
    conn.close()

    resolve_profile("test_profile", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM unresolved_folders WHERE folder_name = 'UnknownArtist'")
    assert cur.fetchone() == ("ignored",)
    conn.close()
