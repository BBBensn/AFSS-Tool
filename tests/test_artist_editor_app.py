import json

from afss.artist_editor.app import create_app
from afss.artist_editor.store import load_artists
from afss.db import get_connection, init_schema


def _seed(config_dir):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "artists.json").write_text(
        json.dumps(
            {
                "artists": [
                    {
                        "id": "artist_alpha",
                        "canonical_name": "Alpha",
                        "aliases": ["alpha1"],
                        "default_tags": {"gender_identity": "female", "birth_date": "1998-03"},
                        "real_name": "",
                        "notes": "",
                        "active": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_index_lists_existing_artists(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.get("/artists/")
    assert resp.status_code == 200
    assert b"Alpha" in resp.data


def test_root_redirects_to_artist_index(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/artists/"


def test_new_form_renders(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.get("/artists/new")
    assert resp.status_code == 200
    assert b"canonical_name" in resp.data


def test_new_form_defaults_gender_fields_to_female(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.get("/artists/new")
    assert b'id="gender_identity" name="gender_identity" list="gender-list" value="female"' in resp.data
    assert b'id="sex_assigned_at_birth" name="sex_assigned_at_birth" list="sex-list" value="female"' in resp.data


def test_edit_form_does_not_override_existing_gender(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)  # artist_alpha hat gender_identity 'female' bereits gesetzt
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.get("/artists/edit/artist_alpha")
    # bestehender Wert bleibt weiterhin exakt 'female' (kein Nebeneffekt), nicht neu überschrieben
    assert b'id="gender_identity" name="gender_identity" list="gender-list" value="female"' in resp.data


def test_edit_form_prefills_existing_values(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.get("/artists/edit/artist_alpha")
    assert resp.status_code == 200
    assert b"Alpha" in resp.data
    assert b"alpha1" in resp.data
    assert b'name="birth_year" placeholder="Jahr" min="1900" max="2100" value="1998"' in resp.data
    assert b'name="birth_month" placeholder="Monat" min="1" max="12" value="3"' in resp.data


def test_edit_unknown_id_redirects_with_flash(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.get("/artists/edit/does_not_exist", follow_redirects=True)
    assert resp.status_code == 200
    assert "nicht gefunden".encode() in resp.data


def test_save_creates_new_artist(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.post(
        "/artists/save",
        data={"canonical_name": "Beta Person", "aliases": "beta, betaperson"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    artists = load_artists(config_dir / "artists.json")
    assert len(artists) == 2
    beta = next(a for a in artists if a["canonical_name"] == "Beta Person")
    assert beta["id"] == "artist_beta_person"
    assert beta["aliases"] == ["beta", "betaperson"]


def test_save_updates_existing_without_duplicating(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    client.post(
        "/artists/save",
        data={
            "original_id": "artist_alpha",
            "id": "artist_alpha",
            "canonical_name": "Alpha Updated",
            "gender_identity": "trans",
        },
    )

    artists = load_artists(config_dir / "artists.json")
    assert len(artists) == 1
    assert artists[0]["canonical_name"] == "Alpha Updated"
    assert artists[0]["default_tags"]["gender_identity"] == "trans"


def test_save_creates_matching_db_row(tmp_path):
    """Regression: 'Melanie' war nur in artists.json auffindbar, weil save() nie in die DB
    geschrieben hat - dadurch war sie in DB-gestützten Suchen (Sortier-Studio) unsichtbar."""
    config_dir = tmp_path / "config"
    _seed(config_dir)
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    client.post("/artists/save", data={"canonical_name": "Melanie"})

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT canonical_name FROM artists WHERE id = 'artist_melanie'")
    assert cur.fetchone() == ("Melanie",)
    conn.close()


def test_save_without_canonical_name_shows_error(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.post("/artists/save", data={}, follow_redirects=True)
    assert "darf nicht leer sein".encode() in resp.data

    artists = load_artists(config_dir / "artists.json")
    assert len(artists) == 1  # nichts hinzugefügt


def test_save_with_partial_birth_date(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    client.post(
        "/artists/save",
        data={"canonical_name": "Only Year Known", "birth_year": "2001"},
    )

    artists = load_artists(config_dir / "artists.json")
    entry = next(a for a in artists if a["canonical_name"] == "Only Year Known")
    assert entry["default_tags"]["birth_date"] == "2001"


def test_parse_bio_route_returns_parsed_fields(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.post(
        "/artists/parse-bio",
        data={"source": "babepedia", "text": "Hair color: Brown\nEye color: Grey"},
    )

    assert resp.status_code == 200
    assert resp.get_json() == {"hair_color": "brown", "eye_color": "grey"}


def test_parse_bio_route_empty_text_returns_empty_json(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.post("/artists/parse-bio", data={"source": "babepedia", "text": ""})

    assert resp.status_code == 200
    assert resp.get_json() == {}


def test_delete_removes_artist(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.post("/artists/delete/artist_alpha", follow_redirects=True)
    assert resp.status_code == 200
    assert "gelöscht".encode() in resp.data
    assert load_artists(config_dir / "artists.json") == []


def test_delete_unknown_id_shows_error(tmp_path):
    config_dir = tmp_path / "config"
    _seed(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.post("/artists/delete/does_not_exist", follow_redirects=True)
    assert "nicht gefunden".encode() in resp.data
    assert len(load_artists(config_dir / "artists.json")) == 1


def _seed_two(config_dir):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "artists.json").write_text(
        json.dumps(
            {
                "artists": [
                    {"id": "artist_alpha", "canonical_name": "Alpha", "aliases": ["alpha1"], "default_tags": {}},
                    {"id": "artist_alpha_dup", "canonical_name": "Alpha Dup", "aliases": [], "default_tags": {}},
                ]
            }
        ),
        encoding="utf-8",
    )


def test_search_returns_matching_artists_excluding_self(tmp_path):
    config_dir = tmp_path / "config"
    _seed_two(config_dir)
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    resp = client.get("/artists/search?q=alpha&exclude=artist_alpha_dup")

    assert resp.status_code == 200
    assert resp.get_json() == [{"id": "artist_alpha", "canonical_name": "Alpha"}]


def test_field_values_returns_matching_nationality_values(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "artists.json").write_text(
        json.dumps(
            {
                "artists": [
                    {"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {"nationality": "aut"}},
                    {"id": "a2", "canonical_name": "B", "aliases": [], "default_tags": {"nationality": "deu"}},
                ]
            }
        ),
        encoding="utf-8",
    )
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.get("/artists/field-values?field=nationality&q=a")

    assert resp.status_code == 200
    assert resp.get_json() == ["aut"]


def test_field_values_rejects_field_outside_allow_list(tmp_path):
    """Verhindert beliebige Feldpfad-Traversierung ueber die Query - nur die explizit fuers
    Autocomplete vorgesehenen Felder duerfen abgefragt werden."""
    config_dir = tmp_path / "config"
    _seed_two(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.get("/artists/field-values?field=id&q=a")

    assert resp.status_code == 200
    assert resp.get_json() == []


def test_merge_moves_source_into_target_and_redirects_to_target(tmp_path):
    config_dir = tmp_path / "config"
    _seed_two(config_dir)
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/artists/merge/artist_alpha_dup",
        data={"target_id": "artist_alpha"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "gemerged".encode() in resp.data
    artists = load_artists(config_dir / "artists.json")
    assert {a["id"] for a in artists} == {"artist_alpha"}
    alpha = next(a for a in artists if a["id"] == "artist_alpha")
    assert "Alpha Dup" in alpha["aliases"]


def test_merge_without_target_shows_error(tmp_path):
    config_dir = tmp_path / "config"
    _seed_two(config_dir)
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    resp = client.post("/artists/merge/artist_alpha_dup", data={}, follow_redirects=True)

    assert "bitte einen Ziel-Artist auswählen".encode() in resp.data
    assert len(load_artists(config_dir / "artists.json")) == 2


def test_merge_unknown_target_shows_error_and_keeps_both(tmp_path):
    config_dir = tmp_path / "config"
    _seed_two(config_dir)
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    app = create_app(config_dir, db_path)
    client = app.test_client()

    resp = client.post(
        "/artists/merge/artist_alpha_dup",
        data={"target_id": "does_not_exist"},
        follow_redirects=True,
    )

    assert "Merge fehlgeschlagen".encode() in resp.data
    assert len(load_artists(config_dir / "artists.json")) == 2


def test_bulk_sets_field_on_selected_artists(tmp_path):
    config_dir = tmp_path / "config"
    _seed_two(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.post(
        "/artists/bulk",
        data={"artist_id": ["artist_alpha", "artist_alpha_dup"], "field": "occupation", "value": "Model, Actress"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "bei 2 Artist(s)".encode() in resp.data
    artists = {a["id"]: a for a in load_artists(config_dir / "artists.json")}
    assert artists["artist_alpha"]["default_tags"]["occupation"] == ["model", "actress"]
    assert artists["artist_alpha_dup"]["default_tags"]["occupation"] == ["model", "actress"]


def test_bulk_without_selection_shows_error(tmp_path):
    config_dir = tmp_path / "config"
    _seed_two(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.post("/artists/bulk", data={"field": "nationality", "value": "usa"}, follow_redirects=True)

    assert "keine Artists ausgewählt".encode() in resp.data


def test_bulk_rejects_field_outside_allow_list(tmp_path):
    config_dir = tmp_path / "config"
    _seed_two(config_dir)
    app = create_app(config_dir)
    client = app.test_client()

    resp = client.post(
        "/artists/bulk",
        data={"artist_id": ["artist_alpha"], "field": "id", "value": "hacked"},
        follow_redirects=True,
    )

    assert "Unbekanntes Feld".encode() in resp.data
    artists = load_artists(config_dir / "artists.json")
    assert next(a for a in artists if a["id"] == "artist_alpha")["id"] == "artist_alpha"
