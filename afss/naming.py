import csv
import re
from pathlib import Path

import yaml

from afss.db import get_connection

_PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")
_TOKEN_PATTERN = re.compile(r"\[(?P<optional>[^\[\]]*)\]|\{(?P<required>\w+)\}|(?P<literal>[^\[\]{}]+)")


def render_pattern(pattern: str, values: dict) -> tuple[str, list[str]]:
    """Rendert ein naming_template-Pattern. [..]-Gruppen entfallen komplett, wenn
    ein enthaltener Platzhalter fehlt. Gibt (gerenderter_stem, fehlende_pflichtfelder) zurück.
    """
    parts = []
    missing_required = []

    for match in _TOKEN_PATTERN.finditer(pattern):
        if match.group("optional") is not None:
            segment = match.group("optional")
            placeholders = _PLACEHOLDER_PATTERN.findall(segment)
            if placeholders and all(values.get(p) for p in placeholders):
                parts.append(_PLACEHOLDER_PATTERN.sub(lambda m: str(values[m.group(1)]), segment))
        elif match.group("required") is not None:
            name = match.group("required")
            value = values.get(name)
            if value:
                parts.append(str(value))
            else:
                missing_required.append(name)
        else:
            parts.append(match.group("literal"))

    return "".join(parts), missing_required


def _sanitize_filename(name: str) -> str:
    return name.replace("/", "-").replace("\x00", "").strip()


def plan_profile(profile_id: str, config_dir: Path, db_path: Path | None = None) -> dict:
    template_path = Path(config_dir) / "naming_template.yml"
    if not template_path.exists():
        raise FileNotFoundError(f"naming_template.yml nicht gefunden: {template_path}")
    template = yaml.safe_load(template_path.read_text(encoding="utf-8")) or {}

    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, media_type, ext, filename, artist_id, provider_id, fs_created_at
        FROM media_items WHERE profile_id = ?
        """,
        (profile_id,),
    )
    rows = cur.fetchall()

    cur.execute("SELECT id, canonical_name FROM artists")
    artist_names = dict(cur.fetchall())
    cur.execute("SELECT id, canonical_name FROM providers")
    provider_names = dict(cur.fetchall())

    ready = []
    needs_review = []

    for item_id, media_type, ext, filename, artist_id, provider_id, fs_created_at in rows:
        pattern = (template.get(media_type) or {}).get("pattern")

        if not pattern:
            reason = f"kein naming_template Pattern für media_type={media_type}"
            needs_review.append(
                {"item_id": item_id, "old_filename": filename, "new_filename": None, "reason": reason}
            )
            cur.execute(
                "UPDATE media_items SET planned_filename = NULL, needs_review = 1, review_reason = ? WHERE id = ?",
                (reason, item_id),
            )
            continue

        values = {
            "artist": artist_names.get(artist_id),
            "provider": provider_names.get(provider_id),
            "title": Path(filename).stem,
            "date": (fs_created_at or None) and fs_created_at[:10],
            "year": (fs_created_at or None) and fs_created_at[:4],
            "studio": None,
        }

        stem, missing = render_pattern(pattern, values)
        stem = _sanitize_filename(stem)

        if missing:
            reason = "fehlende Pflichtfelder: " + ", ".join(missing)
            needs_review.append(
                {"item_id": item_id, "old_filename": filename, "new_filename": None, "reason": reason}
            )
            cur.execute(
                "UPDATE media_items SET planned_filename = NULL, needs_review = 1, review_reason = ? WHERE id = ?",
                (reason, item_id),
            )
        else:
            new_filename = f"{stem}{ext or ''}"
            ready.append(
                {"item_id": item_id, "old_filename": filename, "new_filename": new_filename, "reason": None}
            )
            cur.execute(
                "UPDATE media_items SET planned_filename = ?, needs_review = 0, review_reason = NULL WHERE id = ?",
                (new_filename, item_id),
            )

    conn.commit()
    conn.close()

    return {"profile_id": profile_id, "total": len(rows), "ready": ready, "needs_review": needs_review}


def write_plan_report(result: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["status", "old_filename", "new_filename", "reason"])
        for entry in result["ready"]:
            writer.writerow(["ready", entry["old_filename"], entry["new_filename"], ""])
        for entry in result["needs_review"]:
            writer.writerow(["needs_review", entry["old_filename"], "", entry["reason"]])
