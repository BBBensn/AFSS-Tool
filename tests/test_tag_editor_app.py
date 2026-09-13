from afss.db import get_connection, init_schema
from afss.tag_editor.app import create_app


def _seed(db_path):
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p1', '/tmp', '2020-01-01')")
    cur.execute(
        "INSERT INTO media_items(id, profile_id, path, rel_path, filename, tags, scanned_at) "
        "VALUES (1, 'p1', '/a/1.mp4', 'a/1.mp4', '1.mp4', 'Fav, solo', '2020-01-01')"
    )
    cur.execute(
        "INSERT INTO media_items(id, profile_id, path, rel_path, filename, tags, scanned_at) "
        "VALUES (2, 'p1', '/a/2.mp4', 'a/2.mp4', '2.mp4', 'fav', '2020-01-01')"
    )
    conn.commit()
    conn.close()


def test_index_renders_tags_with_counts(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app(db_path)
    client = app.test_client()

    resp = client.get("/tags/")

    assert resp.status_code == 200
    assert b"Fav" in resp.data
    assert b"solo" in resp.data
    assert b"3 unterschiedliche Tags" in resp.data


def test_index_empty_state(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    app = create_app(db_path)
    client = app.test_client()

    resp = client.get("/tags/")

    assert resp.status_code == 200
    assert "Noch keine Tags vergeben".encode() in resp.data


def test_search_returns_matching_tags(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app(db_path)
    client = app.test_client()

    resp = client.get("/tags/search?q=fa")

    assert resp.status_code == 200
    assert resp.get_json() == ["Fav", "fav"]


def test_rename_route_renames_tag_and_redirects(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app(db_path)
    client = app.test_client()

    resp = client.post("/tags/rename", data={"old_tag": "Fav", "new_tag": "favorite"}, follow_redirects=True)

    assert resp.status_code == 200
    assert "geändert".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT tags FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("favorite, solo",)
    conn.close()


def test_rename_route_with_empty_new_tag_deletes(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app(db_path)
    client = app.test_client()

    resp = client.post("/tags/rename", data={"old_tag": "Fav", "new_tag": ""}, follow_redirects=True)

    assert resp.status_code == 200
    assert "entfernt".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT tags FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("solo",)
    conn.close()


def test_rename_route_without_old_tag_shows_error(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app(db_path)
    client = app.test_client()

    resp = client.post("/tags/rename", data={"old_tag": "", "new_tag": "x"}, follow_redirects=True)

    assert resp.status_code == 200
    assert "Bitte einen vorhandenen Tag".encode() in resp.data
