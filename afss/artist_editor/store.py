import json
import re
from pathlib import Path

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Underscore-getrennter Slug, passend zur bestehenden ID-Konvention (z.B. 'artist_eden_ivy').
    Bewusst anders als normalize_name() (Alias-Matching), das Wortgrenzen nicht erhält."""
    slug = _SLUG_NON_ALNUM.sub("_", name.lower()).strip("_")
    return slug

DEFAULT_TAGS = {
    "gender_identity": "",
    "sex_assigned_at_birth": "",
    "birth_date": "",
    "occupation": [],
    "birth_place": {"city": "", "state": "", "country_iso": ""},
    "nationality": "",
    "ethnicity": "",
    "height_cm": "",
    "weight_kg": "",
    "body_measurements_cm": {"bust_cm": "", "waist_cm": "", "hips_cm": ""},
    "bra_size_eu": "",
    "boobs_type": "",
    "body_type": "",
    "hair_color": "",
    "eye_color": "",
    "artist_tags": [],
    "pierce_locations": [],
    "number_videos": None,
    "number_videos_is_lower_bound": False,
    "active_since_year": None,
    "active_until_year": None,
    "is_currently_active": True,
    "priority": "",
}


def load_artists(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("artists", [])


def save_artists(path: Path, artists: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps({"artists": artists}, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def tags_with_defaults(existing: dict) -> dict:
    """Füllt fehlende default_tags-Felder auf, damit das Formular immer alle Felder zeigt
    (auch für Alt-Einträge, die vor einer Schema-Erweiterung angelegt wurden)."""
    merged = dict(DEFAULT_TAGS)
    merged.update(existing or {})
    merged["birth_place"] = {**DEFAULT_TAGS["birth_place"], **(existing or {}).get("birth_place", {})}
    merged["body_measurements_cm"] = {
        **DEFAULT_TAGS["body_measurements_cm"],
        **(existing or {}).get("body_measurements_cm", {}),
    }
    return merged


def _parse_csv_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_int(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def artist_from_form(form) -> dict:
    return {
        "id": form.get("id", "").strip(),
        "canonical_name": form.get("canonical_name", "").strip(),
        "aliases": _parse_csv_list(form.get("aliases", "")),
        "default_tags": {
            "gender_identity": form.get("gender_identity", "").strip(),
            "sex_assigned_at_birth": form.get("sex_assigned_at_birth", "").strip(),
            "birth_date": form.get("birth_date", "").strip(),
            "occupation": _parse_csv_list(form.get("occupation", "")),
            "birth_place": {
                "city": form.get("birth_place_city", "").strip(),
                "state": form.get("birth_place_state", "").strip(),
                "country_iso": form.get("birth_place_country_iso", "").strip(),
            },
            "nationality": form.get("nationality", "").strip(),
            "ethnicity": form.get("ethnicity", "").strip(),
            "height_cm": form.get("height_cm", "").strip(),
            "weight_kg": form.get("weight_kg", "").strip(),
            "body_measurements_cm": {
                "bust_cm": form.get("bust_cm", "").strip(),
                "waist_cm": form.get("waist_cm", "").strip(),
                "hips_cm": form.get("hips_cm", "").strip(),
            },
            "bra_size_eu": form.get("bra_size_eu", "").strip(),
            "boobs_type": form.get("boobs_type", "").strip(),
            "body_type": form.get("body_type", "").strip(),
            "hair_color": form.get("hair_color", "").strip(),
            "eye_color": form.get("eye_color", "").strip(),
            "artist_tags": _parse_csv_list(form.get("artist_tags", "")),
            "pierce_locations": _parse_csv_list(form.get("pierce_locations", "")),
            "number_videos": _parse_int(form.get("number_videos", "")),
            "number_videos_is_lower_bound": form.get("number_videos_is_lower_bound") == "on",
            "active_since_year": _parse_int(form.get("active_since_year", "")),
            "active_until_year": _parse_int(form.get("active_until_year", "")),
            "is_currently_active": form.get("is_currently_active") == "on",
            "priority": form.get("priority", "").strip(),
        },
        "real_name": form.get("real_name", "").strip(),
        "notes": form.get("notes", "").strip(),
        "active": form.get("active") == "on",
    }


def upsert_artist(path: Path, new_entry: dict, original_id: str | None) -> None:
    artists = load_artists(path)
    if original_id:
        artists = [a for a in artists if a["id"] != original_id]
    artists = [a for a in artists if a["id"] != new_entry["id"]]
    artists.append(new_entry)
    artists.sort(key=lambda a: a["canonical_name"].lower())
    save_artists(path, artists)
