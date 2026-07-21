import json

from afss.artist_editor.app import create_app
from afss.artist_editor.store import load_artists


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
    assert resp.get_json() == {"hair_color": "Brown", "eye_color": "Grey"}


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
