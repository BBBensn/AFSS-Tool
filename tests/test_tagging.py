from afss.db import get_connection, init_schema
from afss.tagging import (
    assign_to_existing_entity,
    assign_to_new_entity,
    get_pending_unresolved,
    get_trash_folder_names,
    ignore_folder,
    search_entities,
    set_category,
    set_trash,
)


def _seed_unresolved(db_path, folder_name="SomeFolder", level=1, profile_id="p1"):
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, sample_path, status)
        VALUES (?, ?, ?, 3, 'sample/path', 'pending')
        """,
        (profile_id, folder_name, level),
    )
    unresolved_id = cur.lastrowid
    conn.commit()
    conn.close()
    return unresolved_id


def test_assign_to_new_entity_creates_artist_and_alias(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    unresolved_id = _seed_unresolved(db_path, folder_name="New Artist")

    entity_id, conflict = assign_to_new_entity(unresolved_id, "artist", "New Artist", db_path)

    assert conflict is None
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT canonical_name FROM artists WHERE id = ?", (entity_id,))
    assert cur.fetchone()[0] == "New Artist"
    cur.execute("SELECT artist_id FROM artist_aliases WHERE alias = 'newartist'")
    assert cur.fetchone()[0] == entity_id
    cur.execute("SELECT status, resolved_to_id FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    assert cur.fetchone() == ("assigned_artist", entity_id)
    conn.close()


def test_assign_to_existing_entity_adds_alias(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO providers(id, canonical_name, tags_json) VALUES ('prov_1', 'Provider One', NULL)")
    conn.commit()
    conn.close()

    unresolved_id = _seed_unresolved(db_path, folder_name="ProvAlias")
    conflict = assign_to_existing_entity(unresolved_id, "provider", "prov_1", db_path)

    assert conflict is None
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT provider_id FROM provider_aliases WHERE alias = 'provalias'")
    assert cur.fetchone()[0] == "prov_1"
    cur.execute("SELECT status, resolved_to_id FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    assert cur.fetchone() == ("assigned_provider", "prov_1")
    conn.close()


def test_assign_detects_alias_conflict_without_overwriting(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('artist_a', 'Artist A', NULL)")
    cur.execute(
        "INSERT INTO artist_aliases(alias, alias_raw, artist_id) VALUES ('sharedname', 'SharedName', 'artist_a')"
    )
    conn.commit()
    conn.close()

    unresolved_id = _seed_unresolved(db_path, folder_name="SharedName")
    entity_id, conflict = assign_to_new_entity(unresolved_id, "artist", "Artist B", db_path)

    assert conflict is not None
    assert conflict["conflict_with"] == "artist_a"

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id FROM artist_aliases WHERE alias = 'sharedname'")
    assert cur.fetchone()[0] == "artist_a"
    cur.execute("SELECT status, resolved_to_id FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    assert cur.fetchone() == ("assigned_artist", entity_id)
    conn.close()


def test_ignore_folder_sets_status(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    unresolved_id = _seed_unresolved(db_path)

    ignore_folder(unresolved_id, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status, resolved_to_id FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    assert cur.fetchone() == ("ignored", None)
    conn.close()


def test_get_pending_unresolved_sorted_by_occurrence(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('p1', 'Low', 1, 1, 'pending')"
    )
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('p1', 'High', 1, 10, 'pending')"
    )
    conn.commit()
    conn.close()

    rows = get_pending_unresolved("p1", db_path)
    assert [r[1] for r in rows] == ["High", "Low"]


def test_set_category_sets_status(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    unresolved_id = _seed_unresolved(db_path, folder_name="Chat")

    set_category(unresolved_id, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status, resolved_to_id FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    assert cur.fetchone() == ("category", None)
    conn.close()


def test_set_trash_sets_status_and_records_name(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    unresolved_id = _seed_unresolved(db_path, folder_name="$RECYCLE.BIN")

    set_trash(unresolved_id, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status, resolved_to_id FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    assert cur.fetchone() == ("trash", None)
    conn.close()

    assert get_trash_folder_names(db_path) == {"recyclebin"}


def test_set_trash_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    unresolved_id = _seed_unresolved(db_path, folder_name="$RECYCLE.BIN")

    set_trash(unresolved_id, db_path)
    set_trash(unresolved_id, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM trash_folder_names")
    assert cur.fetchone()[0] == 1
    conn.close()


def test_search_entities(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('a1', 'Alpha Artist', NULL)")
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('a2', 'Beta Artist', NULL)")
    conn.commit()
    conn.close()

    results = search_entities("artist", "Alpha", db_path)
    assert results == [("a1", "Alpha Artist")]
