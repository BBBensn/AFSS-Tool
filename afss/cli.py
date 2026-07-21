import argparse
from pathlib import Path

from afss.db import init_schema
from afss.migrate_legacy import migrate_legacy_json
from afss.report import report_dedupe, report_missing, report_needs_review, report_overview
from afss.resolve import resolve_profile
from afss.scan import scan_profile


def cmd_scan(args: argparse.Namespace) -> None:
    init_schema()
    result = scan_profile(args.profile, Path(args.config_dir))
    print(f"Scan abgeschlossen: {result['profile_id']} ({result['root']})")
    print(f"Dateien gesamt: {result['total_files']}")
    for media_type, count in sorted(result["media_type_counts"].items()):
        print(f"  {media_type}: {count}")
    print(
        f"Neue unbekannte Ordner: level1={result['unknown_folder_level1_count']}, "
        f"level2={result['unknown_folder_level2_count']}"
    )


def cmd_resolve(args: argparse.Namespace) -> None:
    init_schema()
    result = resolve_profile(args.profile)
    pct = (result["resolved"] / result["total"] * 100) if result["total"] else 0.0
    print(f"{result['resolved']} von {result['total']} Items resolved ({pct:.1f}%)")
    if result["top_unresolved"]:
        print("Häufigste unresolved Ordner:")
        for folder_name, level, count in result["top_unresolved"]:
            print(f"  [level{level}] {folder_name}  ({count}x)")


def cmd_migrate_legacy_json(args: argparse.Namespace) -> None:
    init_schema()
    result = migrate_legacy_json(Path(args.config_dir))
    for kind in ("artists", "providers"):
        r = result[kind]
        print(f"{kind}: {r['imported']} importiert")
        if r["conflicts"]:
            print(f"  {len(r['conflicts'])} Alias-Konflikte:")
            for c in r["conflicts"]:
                print(
                    f"    '{c['alias_raw']}' -> bereits {c['existing_id']}, "
                    f"jetzt auch bei {c['new_id']} (NICHT überschrieben)"
                )


def cmd_report(args: argparse.Namespace) -> None:
    init_schema()
    if args.missing:
        rows = report_missing(args.profile)
        print(f"{len(rows)} Items ohne artist_id:")
        for profile_id, rel_path, folder_level1, folder_level2 in rows:
            print(f"  [{profile_id}] {rel_path}  (level1={folder_level1}, level2={folder_level2})")
        return

    if args.needs_review:
        rows = report_needs_review(args.profile)
        print(f"{len(rows)} Items mit needs_review:")
        for profile_id, rel_path, reason in rows:
            print(f"  [{profile_id}] {rel_path}  ({reason})")
        return

    if args.dedupe:
        rows = report_dedupe(args.profile)
        print(f"{len(rows)} offene Dedupe-Gruppen:")
        for file_hash, member_count, kept_id in rows:
            print(f"  {file_hash[:12]}...  {member_count} Kopien, kept={kept_id}")
        return

    results = report_overview(args.profile)
    if not results:
        print("Keine Daten gefunden.")
        return
    for r in results:
        pct = (r["resolved"] / r["total"] * 100) if r["total"] else 0.0
        print(f"[{r['profile_id']}] {r['total']} Dateien, {r['resolved']} resolved ({pct:.1f}%)")
        for media_type, count in sorted(r["media_type_counts"].items()):
            print(f"  {media_type}: {count}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="afss", description="AFSS media consolidation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Legacy-Root scannen und media_items befüllen")
    p_scan.add_argument("--profile", required=True, help="Profile id aus legacy_profiles.yml")
    p_scan.add_argument("--config-dir", default="config", help="Config-Verzeichnis (Standard: ./config)")
    p_scan.set_defaults(func=cmd_scan)

    p_resolve = sub.add_parser("resolve", help="Ordnernamen gegen Artist/Provider-Aliase matchen")
    p_resolve.add_argument("--profile", required=True, help="Profile id")
    p_resolve.set_defaults(func=cmd_resolve)

    p_migrate = sub.add_parser("migrate-legacy-json", help="artists.json/providers.json einmalig importieren")
    p_migrate.add_argument("--config-dir", default="config", help="Config-Verzeichnis (Standard: ./config)")
    p_migrate.set_defaults(func=cmd_migrate_legacy_json)

    p_report = sub.add_parser("report", help="Statusübersichten")
    p_report.add_argument("--profile", default=None, help="Auf ein Profil einschränken")
    p_report.add_argument("--missing", action="store_true", help="Items ohne artist_id anzeigen")
    p_report.add_argument("--dedupe", action="store_true", help="Offene Dedupe-Gruppen anzeigen")
    p_report.add_argument("--needs-review", action="store_true", help="Items mit needs_review anzeigen")
    p_report.set_defaults(func=cmd_report)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
