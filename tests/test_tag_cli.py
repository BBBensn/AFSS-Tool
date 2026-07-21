from afss.db import get_connection, init_schema
from afss.tag_cli import run_interactive_tag


def _seed(db_path, folder_name="Weird Folder"):
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('p1', ?, 1, 5, 'pending')",
        (folder_name,),
    )
    conn.commit()
    conn.close()


def test_interactive_new_artist_flow(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    answers = iter(["a", "Weird Folder", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    run_interactive_tag("p1", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status, collection_override FROM unresolved_folders WHERE folder_name = 'Weird Folder'")
    assert cur.fetchone() == ("assigned_artist", None)
    conn.close()


def test_interactive_new_artist_with_collection_override(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _seed(db_path, folder_name="Artist Shoot2025")

    answers = iter(["a", "Real Name", "Shoot2025"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    run_interactive_tag("p1", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT status, collection_override FROM unresolved_folders WHERE folder_name = 'Artist Shoot2025'"
    )
    assert cur.fetchone() == ("assigned_artist", "Shoot2025")
    conn.close()


def test_interactive_ignore_flow(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _seed(db_path)

    answers = iter(["i"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    run_interactive_tag("p1", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM unresolved_folders WHERE folder_name = 'Weird Folder'")
    assert cur.fetchone()[0] == "ignored"
    conn.close()
