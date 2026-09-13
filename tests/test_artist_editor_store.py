import json

from werkzeug.datastructures import MultiDict

from afss.artist_editor.store import (
    artist_from_form,
    bulk_set_field,
    delete_artist,
    distinct_field_values,
    load_artists,
    parse_partial_date,
    save_artists,
    search_artists,
    serialize_partial_date,
    sync_artist_to_db,
    tags_with_defaults,
    upsert_artist,
)
from afss.db import get_connection, init_schema


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
            "sexual_orientation": "Pansexual",
            "birth_year": "1995",
            "birth_month": "5",
            "birth_day": "20",
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
    assert tags["sexual_orientation"] == "pansexual"
    assert tags["birth_date"] == "1995-05-20"
    assert tags["occupation"] == ["actress", "model"]
    # Freitext-Attribute werden konsequent lowercase gespeichert (Vienna -> vienna),
    # passend zur bestehenden artists.json-Konvention.
    assert tags["birth_place"] == {"city": "vienna", "state": "", "country_iso": "aut"}
    assert tags["body_measurements_cm"] == {"bust_cm": "90", "waist_cm": "60", "hips_cm": "88"}
    assert tags["bra_size_eu"] == "75b"
    assert tags["number_videos"] == 42
    assert tags["number_videos_is_lower_bound"] is True
    assert tags["active_since_year"] == 2020
    assert tags["active_until_year"] is None
    assert tags["is_currently_active"] is True


def test_artist_from_form_lowercases_freetext_attributes_but_not_proper_nouns():
    form = MultiDict(
        {
            "canonical_name": "Some Artist",
            "aliases": "Some Alias, ANOTHER Alias",
            "real_name": "Jane Doe",
            "notes": "Written As Typed",
            "gender_identity": "Female",
            "ethnicity": "Caucasian",
            "hair_color": "Brown",
            "body_type": "SLIM",
        }
    )
    entry = artist_from_form(form)

    # Eigennamen/Freitext bleiben unangetastet:
    assert entry["canonical_name"] == "Some Artist"
    assert entry["aliases"] == ["Some Alias", "ANOTHER Alias"]
    assert entry["real_name"] == "Jane Doe"
    assert entry["notes"] == "Written As Typed"

    # Attribut-Felder werden lowercase erzwungen:
    tags = entry["default_tags"]
    assert tags["gender_identity"] == "female"
    assert tags["ethnicity"] == "caucasian"
    assert tags["hair_color"] == "brown"
    assert tags["body_type"] == "slim"


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
    assert merged["sexual_orientation"] == ""


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


def test_artist_from_form_year_only_birth_date():
    form = MultiDict({"canonical_name": "Someone", "birth_year": "1998"})
    entry = artist_from_form(form)
    assert entry["default_tags"]["birth_date"] == "1998"


def test_artist_from_form_no_birth_date_when_all_empty():
    form = MultiDict({"canonical_name": "Someone"})
    entry = artist_from_form(form)
    assert entry["default_tags"]["birth_date"] == ""


def test_artist_from_form_day_without_month_is_ignored():
    """Tag ohne Monat kann nicht sinnvoll serialisiert werden - Monat gewinnt Vorrang, Tag wird verworfen."""
    form = MultiDict({"canonical_name": "Someone", "birth_year": "1998", "birth_day": "15"})
    entry = artist_from_form(form)
    assert entry["default_tags"]["birth_date"] == "1998"


def test_serialize_partial_date_variants():
    assert serialize_partial_date("1998", "3", "15") == "1998-03-15"
    assert serialize_partial_date("1998", "3", "") == "1998-03"
    assert serialize_partial_date("1998", "", "") == "1998"
    assert serialize_partial_date("", "", "") == ""


def test_parse_partial_date_variants():
    assert parse_partial_date("1998-03-15") == {"year": 1998, "month": 3, "day": 15}
    assert parse_partial_date("1998-03") == {"year": 1998, "month": 3, "day": None}
    assert parse_partial_date("1998") == {"year": 1998, "month": None, "day": None}
    assert parse_partial_date("") == {"year": None, "month": None, "day": None}
    assert parse_partial_date("not a date") == {"year": None, "month": None, "day": None}


def test_partial_date_roundtrip():
    original = "1998-03"
    parsed = parse_partial_date(original)
    rebuilt = serialize_partial_date(str(parsed["year"]), str(parsed["month"]), "")
    assert rebuilt == original


def test_delete_artist_removes_entry_and_preserves_others(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [
            {"id": "a1", "canonical_name": "Alpha", "aliases": [], "default_tags": {}},
            {"id": "a2", "canonical_name": "Beta", "aliases": [], "default_tags": {}},
        ],
    )

    result = delete_artist(path, "a1")

    assert result is True
    artists = load_artists(path)
    assert [a["id"] for a in artists] == ["a2"]


def test_delete_artist_returns_false_for_unknown_id(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(path, [{"id": "a1", "canonical_name": "Alpha", "aliases": [], "default_tags": {}}])

    result = delete_artist(path, "does_not_exist")

    assert result is False
    assert len(load_artists(path)) == 1


def test_search_artists_matches_substring_case_insensitive(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [
            {"id": "a1", "canonical_name": "Eden Ivy", "aliases": [], "default_tags": {}},
            {"id": "a2", "canonical_name": "Forest Whore", "aliases": [], "default_tags": {}},
        ],
    )

    results = search_artists(path, "eden")

    assert results == [{"id": "a1", "canonical_name": "Eden Ivy"}]


def test_search_artists_excludes_given_id(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [
            {"id": "a1", "canonical_name": "Eden Ivy", "aliases": [], "default_tags": {}},
            {"id": "a2", "canonical_name": "Eden Ivy Duplicate", "aliases": [], "default_tags": {}},
        ],
    )

    results = search_artists(path, "eden", exclude_id="a2")

    assert results == [{"id": "a1", "canonical_name": "Eden Ivy"}]


def test_search_artists_empty_query_returns_nothing(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(path, [{"id": "a1", "canonical_name": "Eden Ivy", "aliases": [], "default_tags": {}}])

    assert search_artists(path, "") == []


def test_distinct_field_values_reads_top_level_string_field(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [
            {"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {"nationality": "aut"}},
            {"id": "a2", "canonical_name": "B", "aliases": [], "default_tags": {"nationality": "deu"}},
            {"id": "a3", "canonical_name": "C", "aliases": [], "default_tags": {"nationality": "aut"}},
        ],
    )

    assert distinct_field_values(path, "nationality") == ["aut", "deu"]
    assert distinct_field_values(path, "nationality", "de") == ["deu"]


def test_distinct_field_values_reads_nested_path(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [
            {"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {"birth_place": {"country_iso": "aut"}}},
            {"id": "a2", "canonical_name": "B", "aliases": [], "default_tags": {"birth_place": {"country_iso": "usa"}}},
            {"id": "a3", "canonical_name": "C", "aliases": [], "default_tags": {}},
        ],
    )

    assert distinct_field_values(path, "birth_place.country_iso") == ["aut", "usa"]


def test_distinct_field_values_collects_list_field_elements(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [
            {"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {"artist_tags": ["milf", "solo"]}},
            {"id": "a2", "canonical_name": "B", "aliases": [], "default_tags": {"artist_tags": ["solo", "anal"]}},
        ],
    )

    assert distinct_field_values(path, "artist_tags") == ["anal", "milf", "solo"]


def test_distinct_field_values_empty_query_returns_all_sorted(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [
            {"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {"ethnicity": "caucasian"}},
            {"id": "a2", "canonical_name": "B", "aliases": [], "default_tags": {}},
        ],
    )

    assert distinct_field_values(path, "ethnicity") == ["caucasian"]
    assert distinct_field_values(path, "nonexistent.path") == []


def test_bulk_set_field_sets_scalar_on_selected_artists_only(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [
            {"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {"nationality": "aut"}},
            {"id": "a2", "canonical_name": "B", "aliases": [], "default_tags": {"nationality": "deu"}},
            {"id": "a3", "canonical_name": "C", "aliases": [], "default_tags": {}},
        ],
    )

    n = bulk_set_field(path, ["a1", "a3"], "nationality", "USA")

    assert n == 2
    artists = {a["id"]: a for a in load_artists(path)}
    assert artists["a1"]["default_tags"]["nationality"] == "usa"
    assert artists["a3"]["default_tags"]["nationality"] == "usa"
    assert artists["a2"]["default_tags"]["nationality"] == "deu"


def test_bulk_set_field_sets_nested_path(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(path, [{"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {}}])

    bulk_set_field(path, ["a1"], "birth_place.country_iso", "AUT")

    artists = load_artists(path)
    assert artists[0]["default_tags"]["birth_place"]["country_iso"] == "aut"


def test_bulk_set_field_replaces_list_field_from_csv(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [{"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {"occupation": ["old"]}}],
    )

    bulk_set_field(path, ["a1"], "occupation", "Model, Actress")

    artists = load_artists(path)
    assert artists[0]["default_tags"]["occupation"] == ["model", "actress"]


def test_bulk_set_field_empty_value_clears_field(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(
        path,
        [{"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {"nationality": "aut"}}],
    )

    bulk_set_field(path, ["a1"], "nationality", "")

    assert load_artists(path)[0]["default_tags"]["nationality"] == ""


def test_bulk_set_field_unknown_id_updates_nothing(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(path, [{"id": "a1", "canonical_name": "A", "aliases": [], "default_tags": {}}])

    n = bulk_set_field(path, ["does_not_exist"], "nationality", "usa")

    assert n == 0
    assert load_artists(path)[0]["default_tags"] == {}


def test_sync_artist_to_db_creates_new_row(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    sync_artist_to_db({"id": "artist_x", "canonical_name": "Artist X"}, None, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT canonical_name FROM artists WHERE id = 'artist_x'")
    assert cur.fetchone() == ("Artist X",)
    conn.close()


def test_sync_artist_to_db_updates_name_for_same_id(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    sync_artist_to_db({"id": "artist_x", "canonical_name": "Old Name"}, None, db_path)

    sync_artist_to_db({"id": "artist_x", "canonical_name": "New Name"}, "artist_x", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT canonical_name FROM artists WHERE id = 'artist_x'")
    assert cur.fetchone() == ("New Name",)
    cur.execute("SELECT COUNT(*) FROM artists")
    assert cur.fetchone()[0] == 1
    conn.close()


def test_sync_artist_to_db_reassigns_references_on_id_change(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO artists(id, canonical_name, tags_json) VALUES ('old_id', 'Name', NULL)")
    cur.execute("INSERT INTO artist_aliases(alias, alias_raw, artist_id) VALUES ('alias1', 'Alias1', 'old_id')")
    cur.execute("INSERT INTO profiles(id, root_path) VALUES ('p1', '/root')")
    cur.execute(
        "INSERT INTO media_items(profile_id, path, rel_path, filename, artist_id, scanned_at) "
        "VALUES ('p1', '/a', 'a', 'a.mp4', 'old_id', datetime('now'))"
    )
    conn.commit()
    conn.close()

    sync_artist_to_db({"id": "new_id", "canonical_name": "Name"}, "old_id", db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM artists WHERE id = 'old_id'")
    assert cur.fetchone() is None
    cur.execute("SELECT artist_id FROM artist_aliases WHERE alias = 'alias1'")
    assert cur.fetchone() == ("new_id",)
    cur.execute("SELECT artist_id FROM media_items WHERE path = '/a'")
    assert cur.fetchone() == ("new_id",)
    conn.close()


def test_save_artists_is_atomic_write(tmp_path):
    path = tmp_path / "artists.json"
    save_artists(path, [{"id": "a1", "canonical_name": "Alpha", "aliases": [], "default_tags": {}}])

    assert not path.with_suffix(".json.tmp").exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["artists"][0]["canonical_name"] == "Alpha"
