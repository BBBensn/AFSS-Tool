import csv
from pathlib import Path

import yaml

from afss.db import get_connection, init_schema
from afss.naming import plan_profile, render_pattern, write_plan_report


def test_render_pattern_all_present():
    stem, missing = render_pattern(
        "{artist} - [{provider} - ][{date} - ]{title}",
        {"artist": "Artist One", "provider": "ProviderX", "date": "2020-01-01", "title": "clip"},
    )
    assert stem == "Artist One - ProviderX - 2020-01-01 - clip"
    assert missing == []


def test_render_pattern_drops_optional_group_when_missing():
    stem, missing = render_pattern(
        "{artist} - [{provider} - ][{date} - ]{title}",
        {"artist": "Artist One", "provider": None, "date": None, "title": "clip"},
    )
    assert stem == "Artist One - clip"
    assert missing == []


def test_render_pattern_reports_missing_required_field():
    stem, missing = render_pattern("{artist} - {title}", {"artist": None, "title": "clip"})
    assert missing == ["artist"]


def _seed(db_path):
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p1', '/tmp', '2020-01-01')")
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('artist_1', 'Artist One', NULL)")
    cur.execute("INSERT INTO providers(id, canonical_name, tags_json) VALUES ('prov_1', 'ProviderX', NULL)")
    cur.execute(
        """
        INSERT INTO media_items(
            profile_id, path, rel_path, filename, ext, media_type,
            artist_id, provider_id, fs_created_at, scanned_at
        ) VALUES ('p1', '/root/a/clip.mp4', 'a/clip.mp4', 'clip.mp4', '.mp4', 'video',
                  'artist_1', 'prov_1', '2020-05-01T12:00:00', '2020-01-01')
        """
    )
    cur.execute(
        """
        INSERT INTO media_items(
            profile_id, path, rel_path, filename, ext, media_type,
            artist_id, provider_id, fs_created_at, scanned_at
        ) VALUES ('p1', '/root/b/orphan.mp4', 'b/orphan.mp4', 'orphan.mp4', '.mp4', 'video',
                  NULL, NULL, '2020-05-01T12:00:00', '2020-01-01')
        """
    )
    conn.commit()
    conn.close()


def test_plan_profile_builds_filenames_and_flags_missing_artist(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "naming_template.yml").write_text(
        yaml.safe_dump({"video": {"pattern": "{artist} - [{provider} - ]{title}"}}), encoding="utf-8"
    )

    result = plan_profile("p1", config_dir, db_path)

    assert result["total"] == 2
    assert len(result["ready"]) == 1
    assert len(result["needs_review"]) == 1
    assert result["ready"][0]["new_filename"] == "Artist One - ProviderX - clip.mp4"
    assert "artist" in result["needs_review"][0]["reason"]

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT planned_filename, needs_review FROM media_items WHERE filename = 'clip.mp4'")
    assert cur.fetchone() == ("Artist One - ProviderX - clip.mp4", 0)
    cur.execute("SELECT planned_filename, needs_review, review_reason FROM media_items WHERE filename = 'orphan.mp4'")
    planned, needs_review, reason = cur.fetchone()
    assert planned is None
    assert needs_review == 1
    assert "artist" in reason
    conn.close()


def test_write_plan_report_writes_csv(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "naming_template.yml").write_text(
        yaml.safe_dump({"video": {"pattern": "{artist} - [{provider} - ]{title}"}}), encoding="utf-8"
    )

    result = plan_profile("p1", config_dir, db_path)
    output_path = tmp_path / "plan.csv"
    write_plan_report(result, output_path)

    with output_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    statuses = {r["status"] for r in rows}
    assert statuses == {"ready", "needs_review"}
    ready_row = next(r for r in rows if r["status"] == "ready")
    assert ready_row["new_filename"] == "Artist One - ProviderX - clip.mp4"
