import json

from afss.db import get_connection, init_schema
from afss.sort_web.app import create_app


def _seed(db_path, config_dir=None):
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p1', '/tmp', '2020-01-01')")
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('artist_1', 'Artist One', NULL)")
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('artist_2', 'Artist Two', NULL)")
    cur.execute(
        """
        INSERT INTO media_items(id, profile_id, path, rel_path, filename, artist_id, collection_name, scanned_at)
        VALUES (1, 'p1', '/a/1.mp4', 'a/1.mp4', '1.mp4', 'artist_1', 'Shoot A', '2020-01-01')
        """
    )
    conn.commit()
    conn.close()

    if config_dir is not None:
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "artists.json").write_text(
            json.dumps(
                {
                    "artists": [
                        {"id": "artist_1", "canonical_name": "Artist One", "aliases": []},
                        {"id": "artist_2", "canonical_name": "Artist Two", "aliases": []},
                    ]
                }
            ),
            encoding="utf-8",
        )


def test_index_all_shows_files_from_every_profile(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p2', '/tmp2', '2020-01-01')")
    cur.execute(
        """
        INSERT INTO media_items(id, profile_id, path, rel_path, filename, artist_id, collection_name, scanned_at)
        VALUES (2, 'p2', '/b/2.mp4', 'b/2.mp4', '2.mp4', 'artist_1', 'Shoot A', '2020-01-01')
        """
    )
    conn.commit()
    conn.close()

    app = create_app("all", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.get("/sort/all/")

    assert resp.status_code == 200
    assert b"1.mp4" in resp.data
    assert b"2.mp4" in resp.data
    assert b"p1" in resp.data
    assert b"p2" in resp.data


def test_index_renders_tree(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.get("/sort/p1/")

    assert resp.status_code == 200
    assert b"Artist One" in resp.data
    assert b"1.mp4" in resp.data


def test_root_redirects_to_sort_index(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.get("/")

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/sort/p1/"


def test_search_returns_matching_artists(tmp_path):
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.get("/sort/p1/search?kind=artist&q=Two")

    assert resp.status_code == 200
    assert resp.get_json() == [{"id": "artist_2", "name": "Artist Two"}]


def test_search_finds_artist_that_only_exists_in_json(tmp_path):
    """Regression: Artists, die nur über den Artist-Editor angelegt wurden (nicht über die
    Tag-Queue), landen zunächst nur in artists.json, nicht in der DB - die Suche muss sie
    trotzdem finden."""
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    (config_dir / "artists.json").write_text(
        json.dumps(
            {
                "artists": [
                    {"id": "artist_json_only", "canonical_name": "Melanie", "aliases": []},
                ]
            }
        ),
        encoding="utf-8",
    )
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.get("/sort/p1/search?kind=artist&q=Melanie")

    assert resp.get_json() == [{"id": "artist_json_only", "name": "Melanie"}]


def test_bulk_set_artist_creates_missing_db_row_from_json(tmp_path):
    """Regression: Zuweisen eines nur-in-JSON existierenden Artists darf nicht an der
    FK-Constraint auf media_items.artist_id scheitern."""
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    (config_dir / "artists.json").write_text(
        json.dumps({"artists": [{"id": "artist_json_only", "canonical_name": "Melanie", "aliases": []}]}),
        encoding="utf-8",
    )
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "set_artist", "artist_target_id": "artist_json_only"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "neu zugeordnet".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT canonical_name FROM artists WHERE id = 'artist_json_only'")
    assert cur.fetchone() == ("Melanie",)
    cur.execute("SELECT artist_id FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("artist_json_only",)
    conn.close()


def test_bulk_clear_artist_removes_assignment(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post("/sort/p1/bulk", data={"item_id": ["1"], "action": "clear_artist"}, follow_redirects=True)

    assert resp.status_code == 200
    assert "Artist entfernt".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id FROM media_items WHERE id = 1")
    assert cur.fetchone() == (None,)
    conn.close()


def test_bulk_dissolve_collection_moves_name_to_tag(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "dissolve_collection", "dissolve_collection_name": "Shoot A"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "aufgelöst".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT collection_name, tags FROM media_items WHERE id = 1")
    assert cur.fetchone() == (None, "Shoot A")
    conn.close()


def test_bulk_set_artist_reassigns_selected_items(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "set_artist", "artist_target_id": "artist_2"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "neu zugeordnet".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id, manual_override FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("artist_2", 1)
    conn.close()


def test_bulk_set_artist_without_target_shows_error(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "set_artist", "artist_target_id": ""},
        follow_redirects=True,
    )

    assert "Bitte zuerst einen Artist auswählen".encode() in resp.data


def test_bulk_without_selection_shows_error(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post("/sort/p1/bulk", data={"action": "set_artist"}, follow_redirects=True)

    assert "keine Dateien ausgewählt".encode() in resp.data


def test_bulk_clear_override_resets_flag(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE media_items SET manual_override = 1 WHERE id = 1")
    conn.commit()
    conn.close()

    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    client.post("/sort/p1/bulk", data={"item_id": ["1"], "action": "clear_override"})

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT manual_override FROM media_items WHERE id = 1")
    assert cur.fetchone()[0] == 0
    conn.close()


def test_details_saves_title_and_tags(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/details",
        data={"title_1": "Neuer Titel", "tags_1": "solo, pov"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "1 Titel, 1 Tag-Felder gespeichert".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT title_override, tags FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("Neuer Titel", "solo, pov")
    conn.close()


def test_bulk_set_status_marks_trash(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk", data={"item_id": ["1"], "action": "set_status", "item_status": "trash"}, follow_redirects=True
    )

    assert "auf Status".encode() in resp.data and "gesetzt".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT item_status FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("trash",)
    conn.close()


def test_bulk_add_tags_appends_without_duplicates(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE media_items SET tags = 'solo' WHERE id = 1")
    conn.commit()
    conn.close()

    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    client.post("/sort/p1/bulk", data={"item_id": ["1"], "action": "add_tags", "new_tags": "solo, pov"})

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT tags FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("solo, pov",)
    conn.close()


def test_bulk_add_co_artist_creates_db_row_from_json_and_links(tmp_path):
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    (config_dir / "artists.json").write_text(
        json.dumps(
            {
                "artists": [
                    {"id": "artist_1", "canonical_name": "Artist One", "aliases": []},
                    {"id": "artist_2", "canonical_name": "Artist Two", "aliases": []},
                    {"id": "artist_co", "canonical_name": "Co Artist", "aliases": []},
                ]
            }
        ),
        encoding="utf-8",
    )
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "add_co_artist", "co_artist_target_id": "artist_co"},
        follow_redirects=True,
    )

    assert "Co-Artist bei 1 Datei(en) ergänzt".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id FROM media_item_co_artists WHERE media_item_id = 1")
    assert cur.fetchone() == ("artist_co",)
    conn.close()


def test_remove_co_artist_route_deletes_link(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO media_item_co_artists(media_item_id, artist_id) VALUES (1, 'artist_2')")
    conn.commit()
    conn.close()

    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    client.post("/sort/p1/remove-co-artist/1/artist_2")

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_item_co_artists")
    assert cur.fetchone()[0] == 0
    conn.close()
