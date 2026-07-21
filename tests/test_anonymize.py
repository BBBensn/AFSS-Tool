import json
from pathlib import Path

from afss.anonymize import clean_file, declean_file, load_mapping, migrate_legacy_mappings


def test_clean_declean_roundtrip(tmp_path):
    input_path = tmp_path / "notes.txt"
    input_path.write_text("SecretArtist met SecretProvider yesterday.", encoding="utf-8")
    mapping_path = tmp_path / "mapping.json"

    cleaned_path = clean_file(input_path, mapping_path)
    cleaned_text = cleaned_path.read_text(encoding="utf-8")
    assert "SecretArtist" not in cleaned_text
    assert "SecretProvider" not in cleaned_text

    restored_path = declean_file(cleaned_path, mapping_path)
    restored_text = restored_path.read_text(encoding="utf-8")
    assert restored_text == input_path.read_text(encoding="utf-8")


def test_clean_is_idempotent_for_known_tokens(tmp_path):
    input_path = tmp_path / "notes.txt"
    input_path.write_text("SecretArtist appears twice: SecretArtist.", encoding="utf-8")
    mapping_path = tmp_path / "mapping.json"

    clean_file(input_path, mapping_path)
    mapping_after_first = json.loads(mapping_path.read_text(encoding="utf-8"))

    clean_file(input_path, mapping_path)
    mapping_after_second = json.loads(mapping_path.read_text(encoding="utf-8"))

    assert mapping_after_first["original_to_fake"] == mapping_after_second["original_to_fake"]
    assert mapping_after_first["counter"] == mapping_after_second["counter"]


def test_whitelist_prevents_replacement(tmp_path):
    input_path = tmp_path / "notes.txt"
    input_path.write_text("KeepMe should stay, HideMe should not.", encoding="utf-8")
    mapping_path = tmp_path / "mapping.json"

    cleaned_path = clean_file(input_path, mapping_path, extra_whitelist=["KeepMe"])
    cleaned_text = cleaned_path.read_text(encoding="utf-8")

    assert "KeepMe" in cleaned_text
    assert "HideMe" not in cleaned_text


def test_migrate_legacy_mappings_merges_and_prefers_omni(tmp_path):
    json_cleaner_path = tmp_path / "old_mapping.json"
    json_cleaner_path.write_text(
        json.dumps({"forward": {"artistone": "PH_AAAA"}, "reverse": {"PH_AAAA": "ArtistOne"}}),
        encoding="utf-8",
    )
    omni_path = tmp_path / "omni_mapping.json"
    omni_path.write_text(
        json.dumps(
            {
                "original_to_fake": {"ArtistOne": "TOKEN_0001", "ProviderX": "TOKEN_0002"},
                "fake_to_original": {"TOKEN_0001": "ArtistOne", "TOKEN_0002": "ProviderX"},
                "counter": 3,
                "whitelist": [],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "config" / "mapping.json"

    result = migrate_legacy_mappings(json_cleaner_path, omni_path, output_path)

    assert len(result["conflicts"]) == 1
    conflict = result["conflicts"][0]
    assert conflict["original"] == "ArtistOne"
    assert conflict["kept"] == "TOKEN_0001"
    assert conflict["discarded"] == "PH_AAAA"

    merged = load_mapping(output_path)
    assert merged["original_to_fake"]["ArtistOne"] == "TOKEN_0001"
    assert merged["original_to_fake"]["ProviderX"] == "TOKEN_0002"


def test_migrate_legacy_mappings_is_idempotent(tmp_path):
    omni_path = tmp_path / "omni_mapping.json"
    omni_path.write_text(
        json.dumps(
            {
                "original_to_fake": {"ArtistOne": "TOKEN_0001"},
                "fake_to_original": {"TOKEN_0001": "ArtistOne"},
                "counter": 2,
                "whitelist": [],
            }
        ),
        encoding="utf-8",
    )
    json_cleaner_path = tmp_path / "missing.json"
    output_path = tmp_path / "mapping.json"

    migrate_legacy_mappings(json_cleaner_path, omni_path, output_path)
    result = migrate_legacy_mappings(json_cleaner_path, omni_path, output_path)

    assert result["imported"] == 0
    assert result["conflicts"] == []
