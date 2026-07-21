from afss.apply import apply_profile, delete_verified_sources
from afss.db import get_connection, init_schema


def _seed(db_path, source_path, planned_filename="Artist One - clip.mp4", collection_name=None):
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p1', '/tmp', '2020-01-01')")
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('artist_1', 'Artist One', NULL)")
    cur.execute(
        """
        INSERT INTO media_items(
            profile_id, path, rel_path, filename, ext, media_type,
            artist_id, collection_name, planned_filename, needs_review, verified, scanned_at
        ) VALUES ('p1', ?, 'clip.mp4', 'clip.mp4', '.mp4', 'video', 'artist_1', ?, ?, 0, 0, '2020-01-01')
        """,
        (str(source_path), collection_name, planned_filename),
    )
    item_id = cur.lastrowid
    conn.commit()
    conn.close()
    return item_id


def test_apply_nests_collection_as_subfolder(tmp_path):
    db_path = tmp_path / "test.db"
    source = tmp_path / "source" / "clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video content")
    _seed(db_path, source, collection_name="Shoot2025")

    target_dir = tmp_path / "target"
    result = apply_profile("p1", target_dir, db_path)

    assert result["copied"] == 1
    dest = target_dir / "Artist One" / "Shoot2025" / "Artist One - clip.mp4"
    assert dest.exists()


def test_apply_copies_and_verifies(tmp_path):
    db_path = tmp_path / "test.db"
    source = tmp_path / "source" / "clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video content")
    item_id = _seed(db_path, source)

    target_dir = tmp_path / "target"
    result = apply_profile("p1", target_dir, db_path)

    assert result["copied"] == 1
    assert result["verified"] == 1
    assert result["failed"] == []

    dest = target_dir / "Artist One" / "Artist One - clip.mp4"
    assert dest.exists()
    assert dest.read_bytes() == source.read_bytes()
    assert source.exists()  # Quelle bleibt (kein delete-source)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT target_path, verified FROM media_items WHERE id = ?", (item_id,))
    target_path, verified = cur.fetchone()
    assert target_path == str(dest)
    assert verified == 1
    conn.close()


def test_apply_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    source = tmp_path / "source" / "clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video content")
    _seed(db_path, source)

    target_dir = tmp_path / "target"
    first = apply_profile("p1", target_dir, db_path)
    second = apply_profile("p1", target_dir, db_path)

    assert first["copied"] == 1
    assert second["copied"] == 0
    assert second["candidates"] == 0  # bereits verified, kein Kandidat mehr


def test_apply_flags_missing_source(tmp_path):
    db_path = tmp_path / "test.db"
    source = tmp_path / "source" / "clip.mp4"
    _seed(db_path, source)  # Quelle existiert nicht

    result = apply_profile("p1", tmp_path / "target", db_path)

    assert result["copied"] == 0
    assert len(result["failed"]) == 1
    assert "Quelle fehlt" in result["failed"][0]["reason"]


def test_delete_verified_sources_only_deletes_when_target_exists(tmp_path):
    db_path = tmp_path / "test.db"
    source = tmp_path / "source" / "clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video content")
    _seed(db_path, source)

    target_dir = tmp_path / "target"
    apply_profile("p1", target_dir, db_path)

    result = delete_verified_sources("p1", db_path)

    assert result["deleted"] == 1
    assert not source.exists()
    dest = target_dir / "Artist One" / "Artist One - clip.mp4"
    assert dest.exists()


def test_delete_verified_sources_skips_when_target_missing(tmp_path):
    db_path = tmp_path / "test.db"
    source = tmp_path / "source" / "clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video content")
    item_id = _seed(db_path, source)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE media_items SET verified = 1, target_path = ? WHERE id = ?",
        (str(tmp_path / "target" / "does_not_exist.mp4"), item_id),
    )
    conn.commit()
    conn.close()

    result = delete_verified_sources("p1", db_path)

    assert result["deleted"] == 0
    assert result["skipped_missing_target"] == 1
    assert source.exists()
