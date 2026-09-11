from afss.db import get_connection, init_schema
from afss.sort_web.app import create_app


def _seed(db_path):
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
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.get("/sort/p1/search?kind=artist&q=Two")

    assert resp.status_code == 200
    assert resp.get_json() == [{"id": "artist_2", "name": "Artist Two"}]


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


def test_titles_saves_title_override(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post("/sort/p1/titles", data={"title_1": "Neuer Titel"}, follow_redirects=True)

    assert resp.status_code == 200
    assert "1 Titel gespeichert".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT title_override FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("Neuer Titel",)
    conn.close()
