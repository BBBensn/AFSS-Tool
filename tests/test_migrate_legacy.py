import json
from pathlib import Path

from afss.db import get_connection, init_schema
from afss.migrate_legacy import migrate_legacy_json


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_migrate_imports_artists_and_providers(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_json(
        config_dir / "artists.json",
        {
            "artists": [
                {
                    "id": "artist_1",
                    "canonical_name": "Artist One",
                    "aliases": ["A1"],
                    "default_tags": {"gender": "f"},
                }
            ]
        },
    )
    _write_json(
        config_dir / "providers.json",
        {"providers": [{"id": "provider_x", "canonical_name": "ProviderX", "aliases": ["PX"]}]},
    )
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    result = migrate_legacy_json(config_dir, db_path)

    assert result["artists"]["imported"] == 1
    assert result["providers"]["imported"] == 1
    assert result["artists"]["conflicts"] == []

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id FROM artist_aliases WHERE alias = 'a1'")
    assert cur.fetchone()[0] == "artist_1"
    cur.execute("SELECT artist_id FROM artist_aliases WHERE alias = 'artistone'")
    assert cur.fetchone()[0] == "artist_1"
    cur.execute("SELECT tags_json FROM artists WHERE id = 'artist_1'")
    tags_json = cur.fetchone()[0]
    conn.close()
    assert json.loads(tags_json)["default_tags"] == {"gender": "f"}


def test_migrate_reports_conflicts_without_overwriting(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_json(
        config_dir / "artists.json",
        {
            "artists": [
                {"id": "artist_1", "canonical_name": "Artist One", "aliases": ["Shared"]},
                {"id": "artist_2", "canonical_name": "Artist Two", "aliases": ["Shared"]},
            ]
        },
    )
    _write_json(config_dir / "providers.json", {"providers": []})
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    result = migrate_legacy_json(config_dir, db_path)

    assert len(result["artists"]["conflicts"]) == 1
    conflict = result["artists"]["conflicts"][0]
    assert conflict["existing_id"] == "artist_1"
    assert conflict["new_id"] == "artist_2"

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id FROM artist_aliases WHERE alias = 'shared'")
    assert cur.fetchone()[0] == "artist_1"
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_json(
        config_dir / "artists.json",
        {"artists": [{"id": "artist_1", "canonical_name": "Artist One", "aliases": ["A1"]}]},
    )
    _write_json(config_dir / "providers.json", {"providers": []})
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    migrate_legacy_json(config_dir, db_path)
    migrate_legacy_json(config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM artists")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT COUNT(*) FROM artist_aliases")
    assert cur.fetchone()[0] == 2
    conn.close()
