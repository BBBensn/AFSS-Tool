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


def test_assign_new_artist_with_collection_override(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", db_path)
    client = app.test_client()

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM unresolved_folders WHERE folder_name = 'Weird Folder'")
    unresolved_id = cur.fetchone()[0]
    conn.close()

    client.post(
        f"/tag/p1/assign/{unresolved_id}",
        data={"action": "new_artist", "canonical_name": "Real Name", "collection_override": "Shoot2025"},
    )

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT collection_override FROM unresolved_folders WHERE id = ?", (unresolved_id,))
    assert cur.fetchone()[0] == "Shoot2025"
    conn.close()


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


def test_assign_category_and_trash(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('p1', 'Chat', 1, 3, 'pending')"
    )
    chat_id = cur.lastrowid
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('p1', '$RECYCLE.BIN', 1, 3, 'pending')"
    )
    trash_id = cur.lastrowid
    conn.commit()
    conn.close()

    app = create_app("p1", db_path)
    client = app.test_client()

    client.post(f"/tag/p1/assign/{chat_id}", data={"action": "category"})
    client.post(f"/tag/p1/assign/{trash_id}", data={"action": "trash"})

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM unresolved_folders WHERE id = ?", (chat_id,))
    assert cur.fetchone()[0] == "category"
    cur.execute("SELECT status FROM unresolved_folders WHERE id = ?", (trash_id,))
    assert cur.fetchone()[0] == "trash"
    cur.execute("SELECT name_normalized FROM trash_folder_names")
    assert cur.fetchone()[0] == "recyclebin"
    conn.close()


def test_index_shows_suggestion_badges(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('p1', 'Pics', 1, 3, 'pending')"
    )
    conn.commit()
    conn.close()

    app = create_app("p1", db_path)
    client = app.test_client()
    resp = client.get("/tag/p1/")

    assert b"Vorschlag: Kategorie" in resp.data
    assert b"erkannte Vorschl" in resp.data


def test_accept_suggestions_only_applies_pattern_matches(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)  # 'Weird Folder' hat keinen Vorschlag
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('p1', 'Pics', 1, 3, 'pending')"
    )
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('p1', '$RECYCLE.BIN', 1, 3, 'pending')"
    )
    conn.commit()
    conn.close()

    app = create_app("p1", db_path)
    client = app.test_client()
    client.post("/tag/p1/accept_suggestions")

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM unresolved_folders WHERE folder_name = 'Pics'")
    assert cur.fetchone()[0] == "category"
    cur.execute("SELECT status FROM unresolved_folders WHERE folder_name = '$RECYCLE.BIN'")
    assert cur.fetchone()[0] == "trash"
    cur.execute("SELECT status FROM unresolved_folders WHERE folder_name = 'Weird Folder'")
    assert cur.fetchone()[0] == "pending"
    conn.close()
