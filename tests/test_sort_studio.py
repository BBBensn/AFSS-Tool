from afss.db import get_connection, init_schema
from afss.sort_studio import bulk_update, clear_manual_override, get_profile_tree, save_title_overrides


def _seed(db_path):
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p1', '/tmp', '2020-01-01')")
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('artist_1', 'Artist One', NULL)")
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('artist_2', 'Artist Two', NULL)")
    cur.execute("INSERT INTO providers(id, canonical_name, tags_json) VALUES ('prov_1', 'ProviderX', NULL)")
    cur.execute(
        """
        INSERT INTO media_items(id, profile_id, path, rel_path, filename, artist_id, provider_id,
                                 collection_name, scanned_at)
        VALUES (1, 'p1', '/a/1.mp4', 'a/1.mp4', '1.mp4', 'artist_1', 'prov_1', 'Shoot A', '2020-01-01')
        """
    )
    cur.execute(
        """
        INSERT INTO media_items(id, profile_id, path, rel_path, filename, artist_id, provider_id,
                                 collection_name, scanned_at)
        VALUES (2, 'p1', '/a/2.mp4', 'a/2.mp4', '2.mp4', 'artist_1', NULL, 'Shoot A', '2020-01-01')
        """
    )
    cur.execute(
        """
        INSERT INTO media_items(id, profile_id, path, rel_path, filename, artist_id, scanned_at)
        VALUES (3, 'p1', '/b/3.mp4', 'b/3.mp4', '3.mp4', NULL, '2020-01-01')
        """
    )
    conn.commit()
    conn.close()


def test_get_profile_tree_groups_by_artist_and_collection(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    tree = get_profile_tree("p1", db_path)

    assert set(tree.keys()) == {"artist_1", "_unresolved"}
    shoot_a = tree["artist_1"]["collections"]["Shoot A"]
    assert {i["id"] for i in shoot_a["files"]} == {1, 2}
    assert tree["artist_1"]["artist_name"] == "Artist One"
    unresolved = tree["_unresolved"]
    assert unresolved["artist_name"] == "(kein Artist zugeordnet)"


def test_get_profile_tree_excludes_pending_duplicates(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO dedupe_groups(id, file_hash, kept_media_item_id) VALUES (1, 'h', 1)")
    cur.execute("INSERT INTO dedupe_group_members(dedupe_group_id, media_item_id, action) VALUES (1, 2, 'pending')")
    conn.commit()
    conn.close()

    tree = get_profile_tree("p1", db_path)

    shoot_a = tree["artist_1"]["collections"]["Shoot A"]
    assert {i["id"] for i in shoot_a["files"]} == {1}


def test_bulk_update_sets_fields_and_manual_override_flag(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    updated = bulk_update([2, 3], {"artist_id": "artist_2", "collection_name": "New Collection"}, db_path)

    assert updated == 2
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id, collection_name, manual_override FROM media_items WHERE id = 2")
    assert cur.fetchone() == ("artist_2", "New Collection", 1)
    cur.execute("SELECT manual_override FROM media_items WHERE id = 1")
    assert cur.fetchone()[0] == 0
    conn.close()


def test_bulk_update_can_clear_a_field_to_none(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    bulk_update([1], {"collection_name": None}, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT collection_name FROM media_items WHERE id = 1")
    assert cur.fetchone() == (None,)
    conn.close()


def test_bulk_update_noop_without_fields_or_ids(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    assert bulk_update([], {"artist_id": "artist_2"}, db_path) == 0
    assert bulk_update([1], {}, db_path) == 0
    assert bulk_update([1], {"not_allowed": "x"}, db_path) == 0


def test_clear_manual_override_resets_flag_only(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    bulk_update([1], {"artist_id": "artist_2"}, db_path)

    updated = clear_manual_override([1], db_path)

    assert updated == 1
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id, manual_override FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("artist_2", 0)
    conn.close()


def test_save_title_overrides_sets_and_clears(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    updated = save_title_overrides({1: "Schöner Titel", 2: "  "}, db_path)

    assert updated == 2
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT title_override FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("Schöner Titel",)
    cur.execute("SELECT title_override FROM media_items WHERE id = 2")
    assert cur.fetchone() == (None,)
    conn.close()
