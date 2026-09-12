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


def test_index_defaults_details_open_for_small_datasets(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.get("/sort/p1/")

    assert b'class="artist" id="artist-artist_1" open' in resp.data
    assert b"1 Datei(en)" in resp.data


def test_index_defaults_details_closed_for_large_datasets(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p1', '/tmp', '2020-01-01')")
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('artist_1', 'Artist One', NULL)")
    for i in range(1, 152):
        cur.execute(
            "INSERT INTO media_items(profile_id, path, rel_path, filename, artist_id, scanned_at) "
            "VALUES ('p1', ?, ?, ?, 'artist_1', '2020-01-01')",
            (f"/a/{i}.mp4", f"{i}.mp4", f"{i}.mp4"),
        )
    conn.commit()
    conn.close()

    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.get("/sort/p1/")

    assert b'class="artist" id="artist-artist_1" open' not in resp.data
    assert b"eingeklappt" in resp.data


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


def test_index_accepts_sort_query_param(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.get("/sort/p1/?sort=filename")

    assert resp.status_code == 200
    assert b'value="filename" selected' in resp.data


def test_index_falls_back_to_collection_for_unknown_sort_value(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.get("/sort/p1/?sort=nonsense")

    assert resp.status_code == 200
    assert b'value="collection" selected' in resp.data


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


def test_bulk_accepts_large_selection_without_413(tmp_path):
    """Flasks Standardlimit fuer Formulardaten (MAX_FORM_MEMORY_SIZE, 500 KB) greift schon bei ein
    paar tausend ausgewaehlten item_id-Checkboxen in einer grossen profile_id='all'-Ansicht und
    fuehrte zu 'Unerwarteter Fehler: 413 Request Entity Too Large' statt der eigentlichen Aktion -
    create_app() muss dieses Limit fuer das rein lokale Single-User-Tool aufheben."""
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO profiles(id, root_path, created_at) VALUES ('p1', '/tmp', '2020-01-01')")
    cur.executemany(
        "INSERT INTO media_items(profile_id, path, rel_path, filename, scanned_at) VALUES ('p1', ?, ?, ?, '2020-01-01')",
        [(f"/a/{i}.mp4", f"a/{i}.mp4", f"{i}.mp4") for i in range(20000)],
    )
    conn.commit()
    cur.execute("SELECT id FROM media_items")
    ids = [str(r[0]) for r in cur.fetchall()]
    conn.close()

    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ids, "action": "clear_artist", "artist_search_text": "x" * 300000},
    )

    assert resp.status_code == 200
    assert "20000 Datei(en): Artist entfernt.".encode() in resp.data
    assert b"Unerwarteter Fehler" not in resp.data


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


def test_bulk_create_and_set_artist_creates_new_entity(tmp_path):
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "create_and_set_artist", "artist_search_text": "Brand New Artist"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "angelegt".encode() in resp.data
    data = json.loads((config_dir / "artists.json").read_text(encoding="utf-8"))
    assert any(a["canonical_name"] == "Brand New Artist" for a in data["artists"])
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT a.canonical_name FROM media_items m JOIN artists a ON a.id = m.artist_id WHERE m.id = 1")
    assert cur.fetchone() == ("Brand New Artist",)
    conn.close()


def test_bulk_create_and_set_artist_without_name_shows_error(tmp_path):
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "create_and_set_artist", "artist_search_text": ""},
        follow_redirects=True,
    )

    assert "Namen für den neuen Artist".encode() in resp.data


def test_bulk_create_and_set_provider_creates_new_entity(tmp_path):
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "create_and_set_provider", "provider_search_text": "New Site"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "angelegt".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT p.canonical_name FROM media_items m JOIN providers p ON p.id = m.provider_id WHERE m.id = 1")
    assert cur.fetchone() == ("New Site",)
    conn.close()


def test_bulk_apply_all_sets_multiple_fields_at_once(tmp_path):
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={
            "item_id": ["1"],
            "action": "apply_all",
            "artist_target_id": "artist_2",
            "collection_name": "New Collection",
            "item_status": "extra",
            "new_tags": "solo, pov",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Artist".encode() in resp.data and "Collection".encode() in resp.data and "Status".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id, collection_name, item_status, tags FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("artist_2", "New Collection", "extra", "solo, pov")
    conn.close()


def test_bulk_apply_all_creates_new_artist_when_no_existing_match(tmp_path):
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "apply_all", "artist_search_text": "Brand New Person"},
    )

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT a.canonical_name FROM media_items m JOIN artists a ON a.id = m.artist_id WHERE m.id = 1")
    assert cur.fetchone() == ("Brand New Person",)
    conn.close()


def test_bulk_apply_all_skips_untouched_fields(tmp_path):
    """Leere Felder werden bei 'Alles setzen' übersprungen, nicht als Löschen interpretiert -
    anders als beim einzelnen 'Collection setzen'-Button."""
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "apply_all"},
        follow_redirects=True,
    )

    assert "nichts geändert".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id, collection_name FROM media_items WHERE id = 1")
    assert cur.fetchone() == ("artist_1", "Shoot A")  # unverändert
    conn.close()


def test_bulk_renders_page_directly_preserving_sort(tmp_path):
    """Seit dem Umbau auf AJAX-Swaps rendert bulk() die Seite direkt (kein redirect mehr) - das
    JS im Template holt diese Response per fetch() und tauscht nur #app-root aus, damit keine
    echte Navigation (und damit kein Scroll-/Layout-Reset) stattfindet."""
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "set_collection", "collection_name": "X", "sort": "ext"},
    )

    assert resp.status_code == 200
    assert b'id="app-root"' in resp.data
    assert b'value="ext" selected' in resp.data


def test_bulk_create_and_add_co_artist_creates_new_entity(tmp_path):
    db_path = tmp_path / "test.db"
    config_dir = tmp_path / "config"
    _seed(db_path, config_dir)
    app = create_app("p1", config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/sort/p1/bulk",
        data={"item_id": ["1"], "action": "create_and_add_co_artist", "co_artist_search_text": "New Co Artist"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "angelegt".encode() in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT a.canonical_name FROM media_item_co_artists mca JOIN artists a ON a.id = mca.artist_id "
        "WHERE mca.media_item_id = 1"
    )
    assert cur.fetchone() == ("New Co Artist",)
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


def test_toggle_lock_locks_artist(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.post("/sort/p1/toggle-lock/artist_1?locked=1")

    assert resp.status_code == 200
    assert b'id="artist-artist_1"' in resp.data
    assert b'class="artist locked"' in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sort_studio_locks WHERE artist_key = 'artist_1'")
    assert cur.fetchone()[0] == 1
    conn.close()


def test_toggle_lock_unlocks_artist(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()
    client.post("/sort/p1/toggle-lock/artist_1?locked=1")

    resp = client.post("/sort/p1/toggle-lock/artist_1?locked=0")

    assert b'class="artist locked"' not in resp.data
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sort_studio_locks")
    assert cur.fetchone()[0] == 0
    conn.close()


def test_locked_artist_renders_closed_and_disabled_checkboxes(tmp_path):
    db_path = tmp_path / "test.db"
    _seed(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO sort_studio_locks(artist_key, locked_at) VALUES ('artist_1', datetime('now'))")
    conn.commit()
    conn.close()

    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    resp = client.get("/sort/p1/")

    assert b'id="artist-artist_1"' in resp.data
    # locked -> kein "open"-Attribut, obwohl das Profil klein genug fuer default_open waere
    assert b'id="artist-artist_1" open' not in resp.data
    assert b'name="item_id" value="1" disabled' in resp.data


def test_bulk_ignores_disabled_locked_items_not_submitted(tmp_path):
    """Gesperrte Checkboxen sind disabled - Browser senden deaktivierte Formularfelder gar nicht
    erst mit, das reicht bereits aus um gesperrte Artists von Bulk-Aktionen auszuschliessen."""
    db_path = tmp_path / "test.db"
    _seed(db_path, tmp_path / "config")
    app = create_app("p1", tmp_path / "config", db_path)
    client = app.test_client()

    # Simuliert das Verhalten eines Browsers: eine disabled Checkbox wird nie mitgeschickt,
    # daher übergeben wir hier bewusst keine item_id fuer den gesperrten Artist.
    resp = client.post(
        "/sort/p1/bulk",
        data={"action": "clear_artist"},
        follow_redirects=True,
    )

    assert "keine Dateien ausgewählt".encode() in resp.data
