import json

import yaml

from afss.dashboard.app import create_app
from afss.db import get_connection, init_schema


def _setup(tmp_path):
    root = tmp_path / "fake_root"
    (root / "Artist One").mkdir(parents=True)
    (root / "Artist One" / "video1.mp4").write_bytes(b"content")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "legacy_profiles.yml").write_text(
        yaml.safe_dump(
            {"profiles": [{"id": "p1", "description": "Test", "root_path": str(root), "enabled": True}]}
        ),
        encoding="utf-8",
    )
    (config_dir / "artists.json").write_text(
        json.dumps({"artists": [{"id": "artist_1", "canonical_name": "Artist One", "aliases": []}]}),
        encoding="utf-8",
    )
    (config_dir / "providers.json").write_text(json.dumps({"providers": []}), encoding="utf-8")
    (config_dir / "naming_template.yml").write_text(
        yaml.safe_dump({"video": {"pattern": "{artist} - {title}"}}), encoding="utf-8"
    )

    db_path = tmp_path / "test.db"
    init_schema(db_path)
    return config_dir, db_path


def test_index_shows_not_scanned_profile(tmp_path):
    config_dir, db_path = _setup(tmp_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    resp = client.get("/")
    assert resp.status_code == 200
    assert b"p1" in resp.data
    assert "noch nicht gescannt".encode() in resp.data


def test_run_scan_then_resolve_updates_stats(tmp_path):
    config_dir, db_path = _setup(tmp_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    resp = client.post("/run/scan/p1", follow_redirects=True)
    assert resp.status_code == 200
    assert "Dateien gefunden".encode() in resp.data

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE profile_id = 'p1'")
    assert cur.fetchone()[0] == 1
    conn.close()

    resp = client.post("/run/resolve/p1", follow_redirects=True)
    assert b"resolved" in resp.data


def test_tag_link_points_to_profile_scoped_tag_page(tmp_path):
    config_dir, db_path = _setup(tmp_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    resp = client.get("/")
    assert b'href="/tag/p1/"' in resp.data


def test_run_plan_writes_csv(tmp_path, monkeypatch):
    config_dir, db_path = _setup(tmp_path)
    monkeypatch.chdir(tmp_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    client.post("/run/scan/p1")
    client.post("/run/resolve/p1")
    resp = client.post("/run/plan/p1", follow_redirects=True)

    assert (tmp_path / "plan_p1.csv").exists()
    assert b"ready" in resp.data


def test_run_apply_without_target_shows_error(tmp_path):
    config_dir, db_path = _setup(tmp_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    resp = client.post("/run/apply/p1", data={}, follow_redirects=True)
    assert "Zielverzeichnis fehlt".encode() in resp.data


def test_unknown_action_shows_error(tmp_path):
    config_dir, db_path = _setup(tmp_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    resp = client.post("/run/bogus/p1", follow_redirects=True)
    assert "Unbekannte Aktion".encode() in resp.data
