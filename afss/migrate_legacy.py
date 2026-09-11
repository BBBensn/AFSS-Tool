import json
from pathlib import Path

from afss.db import get_connection
from afss.normalize import normalize_name


def _load_entries(path: Path, key: str) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"{path} nicht gefunden")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get(key, [])


def _import_entities(entries: list[dict], table: str, alias_table: str, fk_col: str, cur) -> dict:
    conflicts = []
    imported = 0

    for item in entries:
        entity_id = item.get("id")
        canonical_name = item.get("canonical_name") or item.get("name")
        if not entity_id or not canonical_name:
            continue

        extra = {k: v for k, v in item.items() if k not in ("id", "canonical_name", "aliases")}
        cur.execute(
            f"""
            INSERT INTO {table}(id, canonical_name, tags_json) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                canonical_name=excluded.canonical_name,
                tags_json=excluded.tags_json
            """,
            (entity_id, canonical_name, json.dumps(extra, ensure_ascii=False)),
        )
        imported += 1

        aliases_raw = list(item.get("aliases", [])) + [canonical_name]
        for alias_raw in aliases_raw:
            alias = normalize_name(alias_raw)
            if not alias:
                continue

            cur.execute(f"SELECT {fk_col} FROM {alias_table} WHERE alias = ?", (alias,))
            existing = cur.fetchone()
            if existing and existing[0] != entity_id:
                conflicts.append(
                    {"alias_raw": alias_raw, "alias": alias, "existing_id": existing[0], "new_id": entity_id}
                )
                continue

            cur.execute(
                f"INSERT OR IGNORE INTO {alias_table}(alias, alias_raw, {fk_col}) VALUES (?, ?, ?)",
                (alias, alias_raw, entity_id),
            )

    return {"imported": imported, "conflicts": conflicts}


def migrate_legacy_json(config_dir: Path, db_path: Path | None = None) -> dict:
    config_dir = Path(config_dir)
    artists = _load_entries(config_dir / "artists.json", "artists")
    providers = _load_entries(config_dir / "providers.json", "providers")

    conn = get_connection(db_path)
    cur = conn.cursor()

    artist_result = _import_entities(artists, "artists", "artist_aliases", "artist_id", cur)
    provider_result = _import_entities(providers, "providers", "provider_aliases", "provider_id", cur)

    conn.commit()
    conn.close()

    return {"artists": artist_result, "providers": provider_result}


def _sync_kind_to_json(cur, config_dir: Path, kind: str, table: str, alias_table: str, fk_col: str) -> dict:
    filename, list_key = {"artist": ("artists.json", "artists"), "provider": ("providers.json", "providers")}[kind]
    json_path = Path(config_dir) / filename

    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        data = {}
    data.setdefault(list_key, [])
    entries = data[list_key]
    existing_ids = {e.get("id") for e in entries}

    cur.execute(f"SELECT id, canonical_name FROM {table}")
    added = 0
    for entity_id, canonical_name in cur.fetchall():
        if entity_id in existing_ids:
            continue

        cur.execute(f"SELECT alias_raw FROM {alias_table} WHERE {fk_col} = ?", (entity_id,))
        aliases = sorted({row[0] for row in cur.fetchall() if row[0] and row[0] != canonical_name})

        entry = {
            "id": entity_id,
            "canonical_name": canonical_name,
            "aliases": aliases,
            "default_tags": {},
            "active": True,
        }
        if kind == "artist":
            entry["real_name"] = ""
            entry["notes"] = ""
        entries.append(entry)
        added += 1

    if added:
        tmp_path = json_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(json_path)

    return {"added": added, "total_in_json": len(entries)}


def sync_db_identities_to_json(config_dir: Path, db_path: Path | None = None) -> dict:
    """Ergänzt artists.json/providers.json um Identitäten, die in der SQLite-DB existieren
    (meist über 'Artist neu'/'Provider neu' im Tag-UI angelegt), aber dort noch fehlen - mit
    ihren bekannten Aliases. Bestehende JSON-Einträge werden nie verändert, nur ergänzt.
    Idempotent: bereits vorhandene Einträge (per id) werden übersprungen."""
    config_dir = Path(config_dir)
    conn = get_connection(db_path)
    cur = conn.cursor()

    artist_result = _sync_kind_to_json(cur, config_dir, "artist", "artists", "artist_aliases", "artist_id")
    provider_result = _sync_kind_to_json(cur, config_dir, "provider", "providers", "provider_aliases", "provider_id")

    conn.close()
    return {"artists": artist_result, "providers": provider_result}
