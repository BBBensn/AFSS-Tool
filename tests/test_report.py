from afss.db import get_connection, init_schema
from afss.report import report_overview


def _insert_item(cur, profile_id, filename, artist_id=None, missing_since=None):
    cur.execute(
        """
        INSERT INTO media_items(profile_id, path, rel_path, filename, media_type, artist_id, scanned_at, missing_since)
        VALUES (?, ?, ?, ?, 'video', ?, '2026-01-01T00:00:00', ?)
        """,
        (profile_id, f"/root/{filename}", filename, filename, artist_id, missing_since),
    )


def test_report_overview_counts_missing_on_disk(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p1', '/tmp', '2026-01-01')")
    cur.execute("INSERT INTO artists(id, canonical_name) VALUES ('artist_one', 'Artist One')")
    _insert_item(cur, "p1", "a.mp4")
    _insert_item(cur, "p1", "b.mp4", missing_since="2026-02-01T00:00:00")
    _insert_item(cur, "p1", "c.mp4", artist_id="artist_one")
    conn.commit()
    conn.close()

    results = report_overview(db_path=db_path)

    assert len(results) == 1
    row = results[0]
    assert row["total"] == 3
    assert row["resolved"] == 1
    assert row["missing_on_disk"] == 1


def test_report_overview_missing_on_disk_zero_when_nothing_missing(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p1', '/tmp', '2026-01-01')")
    _insert_item(cur, "p1", "a.mp4")
    conn.commit()
    conn.close()

    results = report_overview(db_path=db_path)

    assert results[0]["missing_on_disk"] == 0
