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
