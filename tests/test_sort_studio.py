import json

from afss.db import get_connection, init_schema
from afss.sort_studio import (
    add_co_artist,
    add_tags,
    bulk_update,
    clear_manual_override,
    get_profile_tree,
    remove_co_artist,
    save_tags,
    save_title_overrides,
    set_item_status,
)


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


def test_set_item_status_marks_trash(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    updated = set_item_status([1, 2], "trash", db_path)

    assert updated == 2
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT item_status FROM media_items WHERE id IN (1, 2)")
    assert {r[0] for r in cur.fetchall()} == {"trash"}
    cur.execute("SELECT item_status FROM media_items WHERE id = 3")
    assert cur.fetchone() == ("active",)
    conn.close()


def test_set_item_status_rejects_unknown_status(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    assert set_item_status([1], "not_a_real_status", db_path) == 0


def test_get_profile_tree_exposes_item_status_and_tags(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE media_items SET item_status = 'extra', tags = 'bts, photo' WHERE id = 3")
    conn.commit()
    conn.close()

    tree = get_profile_tree("p1", db_path)

    item3 = next(i for i in tree["_unresolved"]["collections"]["_none"]["files"] if i["id"] == 3)
    assert item3["item_status"] == "extra"
    assert item3["tags"] == "bts, photo"


def test_save_tags_replaces_and_clears(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    updated = save_tags({1: "solo, pov", 2: "  "}, db_path)

    assert updated == 2
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT tags FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("solo, pov",)
    cur.execute("SELECT tags FROM media_items WHERE id = 2")
    assert cur.fetchone() == (None,)
    conn.close()


def test_add_tags_merges_without_duplicating(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE media_items SET tags = 'solo' WHERE id = 1")
    conn.commit()
    conn.close()

    updated = add_tags([1, 2], ["solo", "pov"], db_path)

    assert updated == 2
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT tags FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("solo, pov",)  # 'solo' war schon da, nicht dupliziert
    cur.execute("SELECT tags FROM media_items WHERE id = 2")
    assert cur.fetchone() == ("solo, pov",)  # hatte noch keine Tags, beide werden ergänzt
    conn.close()


def test_add_co_artist_links_without_changing_primary_artist(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    added = add_co_artist([1], "artist_2", db_path)

    assert added == 1
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("artist_1",)
    cur.execute("SELECT artist_id FROM media_item_co_artists WHERE media_item_id = 1")
    assert cur.fetchone() == ("artist_2",)
    conn.close()


def test_add_co_artist_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    add_co_artist([1], "artist_2", db_path)
    add_co_artist([1], "artist_2", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_item_co_artists WHERE media_item_id = 1")
    assert cur.fetchone()[0] == 1
    conn.close()


def test_add_co_artist_creates_missing_db_row_from_json(tmp_path):
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _seed(db_path)
    (config_dir / "artists.json").write_text(
        json.dumps({"artists": [{"id": "artist_json_only", "canonical_name": "Melanie", "aliases": []}]}),
        encoding="utf-8",
    )

    add_co_artist([1], "artist_json_only", db_path, config_dir)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT canonical_name FROM artists WHERE id = 'artist_json_only'")
    assert cur.fetchone() == ("Melanie",)
    conn.close()


def test_get_profile_tree_includes_co_artists(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    add_co_artist([1], "artist_2", db_path)

    tree = get_profile_tree("p1", db_path)

    item1 = next(i for i in tree["artist_1"]["collections"]["Shoot A"]["files"] if i["id"] == 1)
    assert item1["co_artists"] == [{"id": "artist_2", "name": "Artist Two"}]


def test_remove_co_artist_deletes_link(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    add_co_artist([1], "artist_2", db_path)

    removed = remove_co_artist(1, "artist_2", db_path)

    assert removed == 1
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_item_co_artists")
    assert cur.fetchone()[0] == 0
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
