from pathlib import Path

from afss.db import get_connection, init_schema
from afss.dedupe import apply_dedupe, dedupe_profile


def _seed_profile(cur, profile_id="p1"):
    cur.execute(
        "INSERT OR IGNORE INTO profiles(id, root_path, created_at) VALUES (?, '/tmp', '2020-01-01')",
        (profile_id,),
    )


def _insert_item(cur, path, size_bytes, artist_id=None, provider_id=None, fs_created_at="2020-01-01"):
    cur.execute(
        """
        INSERT INTO media_items(
            profile_id, path, rel_path, filename, ext, media_type, size_bytes,
            artist_id, provider_id, fs_created_at, scanned_at
        ) VALUES ('p1', ?, ?, ?, '.mp4', 'video', ?, ?, ?, ?, '2020-01-01')
        """,
        (str(path), path.name, path.name, size_bytes, artist_id, provider_id, fs_created_at),
    )
    return cur.lastrowid


def test_dedupe_groups_identical_files_and_prefers_resolved_kept(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    file_a = tmp_path / "a.mp4"
    file_b = tmp_path / "b.mp4"
    file_a.write_bytes(b"identical content")
    file_b.write_bytes(b"identical content")

    conn = get_connection(db_path)
    cur = conn.cursor()
    _seed_profile(cur)
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('artist_1', 'Artist', NULL)")
    id_a = _insert_item(cur, file_a, file_a.stat().st_size, artist_id=None)
    id_b = _insert_item(cur, file_b, file_b.stat().st_size, artist_id="artist_1")
    conn.commit()
    conn.close()

    result = dedupe_profile("p1", db_path)

    assert result["hashed_count"] == 2
    assert result["groups"] == 1
    assert result["duplicate_files"] == 1

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT kept_media_item_id FROM dedupe_groups")
    kept_id = cur.fetchone()[0]
    assert kept_id == id_b  # besser aufgelöst (artist_id gesetzt)

    cur.execute("SELECT media_item_id, action FROM dedupe_group_members ORDER BY media_item_id")
    members = dict(cur.fetchall())
    assert members[id_a] == "pending"
    assert members[id_b] == "keep"
    conn.close()


def test_dedupe_ignores_different_sizes(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    file_a = tmp_path / "a.mp4"
    file_b = tmp_path / "b.mp4"
    file_a.write_bytes(b"short")
    file_b.write_bytes(b"a much longer file content")

    conn = get_connection(db_path)
    cur = conn.cursor()
    _seed_profile(cur)
    _insert_item(cur, file_a, file_a.stat().st_size)
    _insert_item(cur, file_b, file_b.stat().st_size)
    conn.commit()
    conn.close()

    result = dedupe_profile("p1", db_path)

    assert result["hashed_count"] == 0
    assert result["groups"] == 0


def test_dedupe_is_idempotent_and_preserves_manual_action(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    file_a = tmp_path / "a.mp4"
    file_b = tmp_path / "b.mp4"
    file_a.write_bytes(b"identical content")
    file_b.write_bytes(b"identical content")

    conn = get_connection(db_path)
    cur = conn.cursor()
    _seed_profile(cur)
    id_a = _insert_item(cur, file_a, file_a.stat().st_size)
    id_b = _insert_item(cur, file_b, file_b.stat().st_size)
    conn.commit()
    conn.close()

    dedupe_profile("p1", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT rowid FROM dedupe_group_members WHERE media_item_id = ? AND action = 'pending'", (id_a,))
    row = cur.fetchone()
    pending_rowid = row[0] if row else None
    if pending_rowid is None:
        cur.execute("SELECT rowid FROM dedupe_group_members WHERE media_item_id = ? AND action = 'pending'", (id_b,))
        pending_rowid = cur.fetchone()[0]
    cur.execute("UPDATE dedupe_group_members SET action = 'delete' WHERE rowid = ?", (pending_rowid,))
    conn.commit()
    conn.close()

    dedupe_profile("p1", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dedupe_group_members")
    assert cur.fetchone()[0] == 2
    cur.execute("SELECT action FROM dedupe_group_members WHERE rowid = ?", (pending_rowid,))
    assert cur.fetchone()[0] == "delete"
    conn.close()


def test_apply_dedupe_deletes_pending_files_only(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    file_a = tmp_path / "a.mp4"
    file_b = tmp_path / "b.mp4"
    file_a.write_bytes(b"identical content")
    file_b.write_bytes(b"identical content")

    conn = get_connection(db_path)
    cur = conn.cursor()
    _seed_profile(cur)
    _insert_item(cur, file_a, file_a.stat().st_size)
    _insert_item(cur, file_b, file_b.stat().st_size)
    conn.commit()
    conn.close()

    dedupe_profile("p1", db_path)
    result = apply_dedupe("p1", db_path)

    assert result["deleted"] == 1
    assert result["missing"] == 0
    remaining = [p for p in (file_a, file_b) if p.exists()]
    assert len(remaining) == 1

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT action FROM dedupe_group_members")
    actions = {r[0] for r in cur.fetchall()}
    assert actions == {"keep", "delete"}
    conn.close()
