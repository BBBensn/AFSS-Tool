from afss.db import get_connection, init_schema
from afss.tag_web.app import create_app


def _seed(db_path):
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('a1', 'Alpha', NULL)")
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('p1', 'Weird Folder', 1, 5, 'pending')"
    )
    conn.commit()
    conn.close()


def test_root_redirects_to_profile_tag_page(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", db_path)
    client = app.test_client()

    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/tag/p1/"


def test_index_lists_pending_rows(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", db_path)
    client = app.test_client()

    resp = client.get("/tag/p1/")
    assert resp.status_code == 200
    assert b"Weird Folder" in resp.data


def test_search_returns_matching_artists(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", db_path)
    client = app.test_client()

    resp = client.get("/tag/p1/search?kind=artist&q=Alp")
    assert resp.status_code == 200
    assert resp.get_json() == [{"id": "a1", "name": "Alpha"}]


def test_assign_new_artist_updates_status_and_redirects(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", db_path)
    client = app.test_client()

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM unresolved_folders WHERE folder_name = 'Weird Folder'")
    unresolved_id = cur.fetchone()[0]
    conn.close()

    resp = client.post(
        f"/tag/p1/assign/{unresolved_id}",
        data={"action": "new_artist", "canonical_name": "Weird Folder"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/tag/p1/"

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status, resolved_to_id FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    status, resolved_to_id = cur.fetchone()
    conn.close()
    assert status == "assigned_artist"
    assert resolved_to_id is not None


def test_assign_ignore_sets_status(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", db_path)
    client = app.test_client()

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM unresolved_folders WHERE folder_name = 'Weird Folder'")
    unresolved_id = cur.fetchone()[0]
    conn.close()

    client.post(f"/tag/p1/assign/{unresolved_id}", data={"action": "ignore"})

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    assert cur.fetchone()[0] == "ignored"
    conn.close()
