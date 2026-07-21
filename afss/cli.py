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


def cmd_anonymize(args: argparse.Namespace) -> None:
    from afss.anonymize import clean_file, declean_file

    input_path = Path(args.file)
    mapping_path = Path(args.mapping)
    if not input_path.exists():
        print(f"[ERROR] Datei nicht gefunden: {input_path}")
        return

    if args.mode == "clean":
        extra_whitelist = [p.strip() for p in args.whitelist.split(",")] if args.whitelist else None
        out_path = clean_file(input_path, mapping_path, extra_whitelist)
        print(f"[OK] Clean-Datei: {out_path}")
    else:
        out_path = declean_file(input_path, mapping_path)
        print(f"[OK] Restored-Datei: {out_path}")


def cmd_migrate_mapping(args: argparse.Namespace) -> None:
    from afss.anonymize import migrate_legacy_mappings

    result = migrate_legacy_mappings(Path(args.json_cleaner), Path(args.omni_cleaner), Path(args.output))
    print(f"{result['imported']} Einträge in {args.output} übernommen.")
    if result["conflicts"]:
        print(f"{len(result['conflicts'])} Konflikte (NICHT übernommen):")
        for c in result["conflicts"]:
            print(f"  '{c['original']}' -> behalten: {c['kept']}, verworfen ({c['source']}): {c['discarded']}")


def cmd_tag(args: argparse.Namespace) -> None:
    init_schema()
    if args.web:
        from afss.tag_web.app import run_web

        print(f"Web-UI läuft auf http://127.0.0.1:{args.port} (nur lokal erreichbar)")
        run_web(args.profile, port=args.port)
    else:
        from afss.tag_cli import run_interactive_tag

        run_interactive_tag(args.profile)


def cmd_dashboard(args: argparse.Namespace) -> None:
    init_schema()
    from afss.dashboard.app import run_dashboard

    print(f"Dashboard läuft auf http://127.0.0.1:{args.port} (nur lokal erreichbar)")
    run_dashboard(Path(args.config_dir), port=args.port)


def cmd_apply(args: argparse.Namespace) -> None:
    init_schema()
    from afss.apply import apply_profile, delete_verified_sources

    result = apply_profile(args.profile, Path(args.target))
    print(
        f"{result['copied']} kopiert, {result['verified']} verifiziert, "
        f"{result['skipped_existing']} bereits vorhanden, {len(result['failed'])} fehlgeschlagen."
    )
    for f in result["failed"]:
        print(f"  [FEHLER] item {f['item_id']}: {f['reason']}")

    if args.delete_source:
        if not args.yes_i_am_sure:
            answer = input("Wirklich alle verifizierten Quelldateien löschen? (j/n) ").strip().lower()
            if answer != "j":
                print("Abgebrochen (Quelldateien bleiben erhalten).")
                return
        del_result = delete_verified_sources(args.profile)
        print(
            f"{del_result['deleted']} Quelldateien gelöscht, "
            f"{del_result['skipped_missing_target']} übersprungen (Ziel fehlt), "
            f"{del_result['missing_source']} Quelle bereits weg."
        )


def cmd_plan(args: argparse.Namespace) -> None:
    init_schema()
    from afss.naming import plan_profile, write_plan_report

    result = plan_profile(args.profile, Path(args.config_dir))
    print(
        f"{len(result['ready'])} von {result['total']} Items geplant (ready), "
        f"{len(result['needs_review'])} needs_review."
    )

    output_path = Path(args.output) if args.output else Path(f"plan_{args.profile}.csv")
    write_plan_report(result, output_path)
    print(f"Report geschrieben: {output_path}")


def cmd_dedupe(args: argparse.Namespace) -> None:
    init_schema()
    from afss.dedupe import apply_dedupe, dedupe_profile

    if args.apply:
        if not args.yes_i_am_sure:
            answer = input(
                f"Wirklich alle 'pending' Duplikate für Profil '{args.profile}' löschen? (j/n) "
            ).strip().lower()
            if answer != "j":
                print("Abgebrochen.")
                return
        result = apply_dedupe(args.profile)
        print(f"{result['deleted']} Dateien gelöscht, {result['missing']} nicht gefunden (übersprungen).")
        return

    result = dedupe_profile(args.profile)
    print(
        f"{result['hashed_count']} Dateien gehasht, {result['groups']} Dedupe-Gruppen, "
        f"{result['duplicate_files']} Duplikate (action=pending) markiert."
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

    p_anon = sub.add_parser("anonymize", help="Text/JSON-Dateien anonymisieren oder wiederherstellen")
    p_anon.add_argument("mode", choices=["clean", "declean"])
    p_anon.add_argument("file")
    p_anon.add_argument("--mapping", default="config/mapping.json", help="Pfad zur mapping.json")
    p_anon.add_argument("--whitelist", default=None, help="Kommaseparierte Phrasen, die nie ersetzt werden (nur clean)")
    p_anon.set_defaults(func=cmd_anonymize)

    p_migrate_map = sub.add_parser(
        "migrate-mapping", help="Alte mapping.json aus json_cleaner + omni_cleaner zusammenführen"
    )
    p_migrate_map.add_argument("--json-cleaner", default="tools/mapping.json", help="Pfad zur json_cleaner mapping.json")
    p_migrate_map.add_argument("--omni-cleaner", default="tools/omni_mapping.json", help="Pfad zur omni_cleaner mapping.json")
    p_migrate_map.add_argument("--output", default="config/mapping.json", help="Zielpfad für konsolidiertes Mapping")
    p_migrate_map.set_defaults(func=cmd_migrate_mapping)

    p_tag = sub.add_parser("tag", help="Unresolved Ordner Artist/Provider zuweisen")
    p_tag.add_argument("--profile", required=True, help="Profile id")
    p_tag.add_argument("--web", action="store_true", help="Lokale Flask-Web-UI statt CLI-Dialog starten")
    p_tag.add_argument("--port", type=int, default=5151, help="Port für --web (Standard: 5151)")
    p_tag.set_defaults(func=cmd_tag)

    p_dashboard = sub.add_parser("dashboard", help="Lokales Web-Dashboard für alle Schritte starten")
    p_dashboard.add_argument("--config-dir", default="config", help="Config-Verzeichnis (Standard: ./config)")
    p_dashboard.add_argument("--port", type=int, default=5150, help="Port (Standard: 5150)")
    p_dashboard.set_defaults(func=cmd_dashboard)

    p_apply = sub.add_parser("apply", help="Verifiziert kopieren (nicht verschieben)")
    p_apply.add_argument("--profile", required=True, help="Profile id")
    p_apply.add_argument("--target", required=True, help="Zielverzeichnis (z.B. Jellyfin-Library)")
    p_apply.add_argument("--delete-source", action="store_true", help="Nach Verifikation Quelldateien löschen")
    p_apply.add_argument(
        "--yes-i-am-sure", action="store_true", help="Bestätigung für --delete-source ohne Rückfrage"
    )
    p_apply.set_defaults(func=cmd_apply)

    p_plan = sub.add_parser("plan", help="Zieldateinamen nach naming_template.yml berechnen")
    p_plan.add_argument("--profile", required=True, help="Profile id")
    p_plan.add_argument("--config-dir", default="config", help="Config-Verzeichnis (Standard: ./config)")
    p_plan.add_argument("--output", default=None, help="Pfad für CSV-Report (Standard: plan_<profile>.csv)")
    p_plan.set_defaults(func=cmd_plan)

    p_dedupe = sub.add_parser("dedupe", help="Duplikate per Datei-Hash finden (löscht nichts automatisch)")
    p_dedupe.add_argument("--profile", required=True, help="Profile id oder 'all'")
    p_dedupe.add_argument("--apply", action="store_true", help="Als 'pending' markierte Duplikate jetzt löschen")
    p_dedupe.add_argument("--yes-i-am-sure", action="store_true", help="Bestätigung für --apply ohne Rückfrage")
    p_dedupe.set_defaults(func=cmd_dedupe)

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
