"""CLI to run legacy profile scan and write results into SQLite DB.

Usage example:
    python -m tools.afss_legacy_import --profile legacy_cat01
"""
from pathlib import Path
import argparse
from core.db import init_schema, get_db_path
from modules.legacy_importer.scan import scan_profile
import sqlite3


def summarize(db_path: Path, profile_id: str) -> None:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        "SELECT media_type, COUNT(*) FROM media_items WHERE legacy_profile_id = ? GROUP BY media_type",
        (profile_id,),
    )
    rows = cur.fetchall()
    conn.close()

    print("Scan abgeschlossen.")
    for media_type, count in sorted(rows):
        # human-friendly label
        label = media_type
        print(f"{label.capitalize()}: {count} Dateien")


def main():
    parser = argparse.ArgumentParser(description="AFSS Legacy Import (scan-only prototype)")
    parser.add_argument("--profile", required=True, help="Profile id from legacy_profiles.yml")
    parser.add_argument("--config-dir", default="config", help="Config directory (default: ./config)")
    parser.add_argument("--db-path", default=None, help="Path to sqlite DB (default: AFSS/afss.db)")

    args = parser.parse_args()

    # initialize schema
    init_schema()

    db_path = Path(args.db_path) if args.db_path else get_db_path()

    # run scan
    counts = scan_profile(args.profile, Path(args.config_dir), db_path)

    # if scan_profile returned counts, print quick inline summary
    if counts:
        print("Inline-Zusammenfassung (vor DB-Abfrage):")
        for k, v in counts.items():
            print(f"  {k}: {v}")

    # print DB-based summary
    summarize(db_path, args.profile)


if __name__ == "__main__":
    main()
