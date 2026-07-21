import json

from werkzeug.datastructures import MultiDict

from afss.artist_editor.store import (
    artist_from_form,
    load_artists,
    save_artists,
    tags_with_defaults,
    upsert_artist,
)


def test_artist_from_form_parses_types_correctly():
    form = MultiDict(
        {
            "id": "artist_test_person",
            "canonical_name": "Test Person",
            "aliases": "Test Person, TestPerson, test_person",
            "real_name": "Jane Doe",
            "active": "on",
            "gender_identity": "female",
            "sex_assigned_at_birth": "female",
            "birth_date": "1995-05-20",
            "occupation": "actress, model",
            "birth_place_city": "Vienna",
            "birth_place_state": "",
            "birth_place_country_iso": "aut",
            "nationality": "aut",
            "ethnicity": "caucasian",
            "height_cm": "170",
            "weight_kg": "58",
            "bust_cm": "90",
            "waist_cm": "60",
            "hips_cm": "88",
            "bra_size_eu": "75B",
            "boobs_type": "natural",
            "body_type": "slim",
            "hair_color": "brown",
            "eye_color": "blue",
            "artist_tags": "tattooed, funny",
            "pierce_locations": "navel, nose",
            "number_videos": "42",
            "number_videos_is_lower_bound": "on",
            "active_since_year": "2020",
            "active_until_year": "",
            "is_currently_active": "on",
            "priority": "main",
            "notes": "Some notes",
        }
    )

    entry = artist_from_form(form)

    assert entry["id"] == "artist_test_person"
    assert entry["canonical_name"] == "Test Person"
    assert entry["aliases"] == ["Test Person", "TestPerson", "test_person"]
    assert entry["active"] is True
    assert entry["notes"] == "Some notes"

    tags = entry["default_tags"]
    assert tags["occupation"] == ["actress", "model"]
    assert tags["birth_place"] == {"city": "Vienna", "state": "", "country_iso": "aut"}
    assert tags["body_measurements_cm"] == {"bust_cm": "90", "waist_cm": "60", "hips_cm": "88"}
    assert tags["number_videos"] == 42
    assert tags["number_videos_is_lower_bound"] is True
    assert tags["active_since_year"] == 2020
    assert tags["active_until_year"] is None
    assert tags["is_currently_active"] is True


def test_artist_from_form_defaults_unchecked_boxes_to_false():
    form = MultiDict({"canonical_name": "Minimal"})
    entry = artist_from_form(form)

    assert entry["active"] is False
    assert entry["default_tags"]["is_currently_active"] is False
    assert entry["default_tags"]["number_videos_is_lower_bound"] is False
    assert entry["default_tags"]["number_videos"] is None
    assert entry["aliases"] == []


def test_tags_with_defaults_fills_missing_keys_for_legacy_entries():
    legacy = {"gender_identity": "female"}
    merged = tags_with_defaults(legacy)

    assert merged["gender_identity"] == "female"
    assert merged["birth_place"] == {"city": "", "state": "", "country_iso": ""}
    assert merged["artist_tags"] == []
    assert merged["is_currently_active"] is True


def test_upsert_artist_appends_new_and_preserves_others(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(path, [{"id": "a1", "canonical_name": "Alpha", "aliases": [], "default_tags": {}}])

    new_entry = {"id": "a2", "canonical_name": "Beta", "aliases": [], "default_tags": {}}
    upsert_artist(path, new_entry, original_id=None)

    artists = load_artists(path)
    assert {a["id"] for a in artists} == {"a1", "a2"}


def test_upsert_artist_replaces_when_editing_existing(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [
            {"id": "a1", "canonical_name": "Alpha", "aliases": [], "default_tags": {}},
            {"id": "a2", "canonical_name": "Beta", "aliases": [], "default_tags": {}},
        ],
    )

    updated = {"id": "a1", "canonical_name": "Alpha Renamed", "aliases": [], "default_tags": {}}
    upsert_artist(path, updated, original_id="a1")

    artists = load_artists(path)
    assert len(artists) == 2
    alpha = next(a for a in artists if a["id"] == "a1")
    assert alpha["canonical_name"] == "Alpha Renamed"


def test_upsert_artist_id_change_removes_old_id(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(path, [{"id": "old_id", "canonical_name": "Alpha", "aliases": [], "default_tags": {}}])

    updated = {"id": "new_id", "canonical_name": "Alpha", "aliases": [], "default_tags": {}}
    upsert_artist(path, updated, original_id="old_id")

    artists = load_artists(path)
    assert [a["id"] for a in artists] == ["new_id"]


def test_save_artists_is_atomic_write(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(path, [{"id": "a1", "canonical_name": "Alpha", "aliases": [], "default_tags": {}}])

    assert not path.with_suffix(".json.tmp").exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["artists"][0]["canonical_name"] == "Alpha"
