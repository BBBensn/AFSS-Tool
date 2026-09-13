import json
import re
from pathlib import Path

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_PARTIAL_DATE = re.compile(r"^(\d{4})(?:-(\d{2}))(?:-(\d{2}))?$|^(\d{4})$")


def slugify(name: str) -> str:
    """Underscore-getrennter Slug, passend zur bestehenden ID-Konvention (z.B. 'artist_eden_ivy').
    Bewusst anders als normalize_name() (Alias-Matching), das Wortgrenzen nicht erhält."""
    return _SLUG_NON_ALNUM.sub("_", name.lower()).strip("_")


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


def parse_partial_date(date_str: str) -> dict:
    """'1998-03-15' -> {year: 1998, month: 3, day: 15}; '1998-03' -> {..., day: None};
    '1998' -> {..., month: None, day: None}; alles andere (leer, unparsebar) -> alle None.
    Geburtsdatum ist oft nur teilweise bekannt - das MUSS abbildbar sein, ohne einen
    erfundenen Monat/Tag vorzutäuschen."""
    if not date_str:
        return {"year": None, "month": None, "day": None}
    match = _PARTIAL_DATE.match(date_str.strip())
    if not match:
        return {"year": None, "month": None, "day": None}
    if match.group(4):  # nur Jahr, z.B. "1998"
        return {"year": int(match.group(4)), "month": None, "day": None}
    year, month, day = match.group(1), match.group(2), match.group(3)
    return {
        "year": int(year) if year else None,
        "month": int(month) if month else None,
        "day": int(day) if day else None,
    }


def serialize_partial_date(year: str, month: str, day: str) -> str:
    """Baut aus (teils leeren) Jahr/Monat/Tag-Feldern einen ISO-8601-Präfix-String.
    Tag ohne Monat wird ignoriert (nicht sinnvoll darstellbar)."""
    year = (year or "").strip()
    month = (month or "").strip()
    day = (day or "").strip()
    if not year:
        return ""
    parts = [year.zfill(4)]
    if month:
        parts.append(month.zfill(2))
        if day:
            parts.append(day.zfill(2))
    return "-".join(parts)


def _parse_csv_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_csv_list_lower(value: str) -> list[str]:
    return [v.strip().lower() for v in value.split(",") if v.strip()]


def _lower(value: str) -> str:
    return (value or "").strip().lower()


def _parse_int(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def artist_from_form(form) -> dict:
    """Freitext-Attribute (Gender, Ethnicity, Farben, ...) werden konsequent lowercase gespeichert,
    passend zur bestehenden artists.json-Konvention. Ausgenommen: canonical_name, aliases, real_name,
    notes, id - das sind Eigennamen/Freitext, deren Groß-/Kleinschreibung bewusst erhalten bleibt."""
    return {
        "id": form.get("id", "").strip(),
        "canonical_name": form.get("canonical_name", "").strip(),
        "aliases": _parse_csv_list(form.get("aliases", "")),
        "default_tags": {
            "gender_identity": _lower(form.get("gender_identity", "")),
            "sex_assigned_at_birth": _lower(form.get("sex_assigned_at_birth", "")),
            "birth_date": serialize_partial_date(
                form.get("birth_year", ""), form.get("birth_month", ""), form.get("birth_day", "")
            ),
            "occupation": _parse_csv_list_lower(form.get("occupation", "")),
            "birth_place": {
                "city": _lower(form.get("birth_place_city", "")),
                "state": _lower(form.get("birth_place_state", "")),
                "country_iso": _lower(form.get("birth_place_country_iso", "")),
            },
            "nationality": _lower(form.get("nationality", "")),
            "ethnicity": _lower(form.get("ethnicity", "")),
            "height_cm": form.get("height_cm", "").strip(),
            "weight_kg": form.get("weight_kg", "").strip(),
            "body_measurements_cm": {
                "bust_cm": form.get("bust_cm", "").strip(),
                "waist_cm": form.get("waist_cm", "").strip(),
                "hips_cm": form.get("hips_cm", "").strip(),
            },
            "bra_size_eu": _lower(form.get("bra_size_eu", "")),
            "boobs_type": _lower(form.get("boobs_type", "")),
            "body_type": _lower(form.get("body_type", "")),
            "hair_color": _lower(form.get("hair_color", "")),
            "eye_color": _lower(form.get("eye_color", "")),
            "artist_tags": _parse_csv_list_lower(form.get("artist_tags", "")),
            "pierce_locations": _parse_csv_list_lower(form.get("pierce_locations", "")),
            "number_videos": _parse_int(form.get("number_videos", "")),
            "number_videos_is_lower_bound": form.get("number_videos_is_lower_bound") == "on",
            "active_since_year": _parse_int(form.get("active_since_year", "")),
            "active_until_year": _parse_int(form.get("active_until_year", "")),
            "is_currently_active": form.get("is_currently_active") == "on",
            "priority": _lower(form.get("priority", "")),
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


def search_artists(path: Path, query: str, exclude_id: str = "") -> list[dict]:
    """Für die Merge-Autocomplete: Kandidaten aus artists.json, nicht aus der DB - die
    Editor-Liste (inkl. rein JSON-only angelegter Duplikate) ist hier die maßgebliche Quelle."""
    query = query.strip().lower()
    if not query:
        return []
    artists = load_artists(path)
    return [
        {"id": a["id"], "canonical_name": a["canonical_name"]}
        for a in artists
        if a["id"] != exclude_id and query in a.get("canonical_name", "").lower()
    ][:25]


def distinct_field_values(artists_path: Path, field_path: str, query: str = "", limit: int = 20) -> list[str]:
    """Liefert bereits vergebene Werte für ein default_tags-Feld (z.B. 'nationality' oder
    'birth_place.country_iso') über alle Artists hinweg - für Autocomplete im Formular, damit nicht
    durch Groß-/Kleinschreibung oder Leerzeichen-Varianten unnötig Nah-Duplikate entstehen (z.B.
    'German' neben 'german '). field_path wird punktgetrennt durch verschachtelte dicts traversiert;
    Listen-Felder (artist_tags, occupation, pierce_locations) werden elementweise eingesammelt."""
    artists = load_artists(artists_path)
    values: set[str] = set()
    parts = field_path.split(".")
    for a in artists:
        node = a.get("default_tags", {})
        for part in parts:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(part)
        if isinstance(node, str) and node.strip():
            values.add(node.strip())
        elif isinstance(node, list):
            for v in node:
                if isinstance(v, str) and v.strip():
                    values.add(v.strip())

    q = query.strip().lower()
    matches = sorted(v for v in values if q in v.lower()) if q else sorted(values)
    return matches[:limit]


def sync_artist_to_db(entry: dict, original_id: str | None, db_path: Path | None = None) -> None:
    """Zieht einen über den Artist-Editor gespeicherten Artist in die SQLite-DB nach - ohne das
    würde 'save' nur artists.json schreiben, und der Artist wäre in DB-gestützten Features (z.B.
    Sortier-Studio-Suche, alias-Matching) unsichtbar, obwohl er im Editor sichtbar existiert.
    Bei einer ID-Änderung werden bestehende artist_aliases/media_items auf die neue ID umgehängt,
    statt die alte DB-Zeile (samt Referenzen) verwaist zurückzulassen."""
    from afss.db import get_connection

    conn = get_connection(db_path)
    cur = conn.cursor()

    # Neue/geänderte ID muss zuerst existieren, bevor Referenzen darauf umgehängt werden können
    # (artist_aliases/media_items haben eine FK auf artists.id).
    cur.execute(
        "INSERT INTO artists(id, canonical_name, tags_json) VALUES (?, ?, NULL) "
        "ON CONFLICT(id) DO UPDATE SET canonical_name = excluded.canonical_name",
        (entry["id"], entry["canonical_name"]),
    )

    if original_id and original_id != entry["id"]:
        cur.execute("SELECT 1 FROM artists WHERE id = ?", (original_id,))
        if cur.fetchone() is not None:
            cur.execute("UPDATE artist_aliases SET artist_id = ? WHERE artist_id = ?", (entry["id"], original_id))
            cur.execute("UPDATE media_items SET artist_id = ? WHERE artist_id = ?", (entry["id"], original_id))
            cur.execute("DELETE FROM artists WHERE id = ?", (original_id,))

    conn.commit()
    conn.close()


def delete_artist(path: Path, artist_id: str) -> bool:
    artists = load_artists(path)
    remaining = [a for a in artists if a["id"] != artist_id]
    if len(remaining) == len(artists):
        return False
    save_artists(path, remaining)
    return True
