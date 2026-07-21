from pathlib import Path

from afss.suggest import suggest_action
from afss.tagging import (
    assign_to_existing_entity,
    assign_to_new_entity,
    get_pending_unresolved,
    ignore_folder,
    search_entities,
    set_category,
    set_trash,
)


def _print_conflict(conflict: dict | None) -> None:
    if conflict:
        print(
            f"[WARN] Alias '{conflict['alias_raw']}' zeigt bereits auf {conflict['conflict_with']} "
            "— Alias wurde NICHT überschrieben."
        )


def run_interactive_tag(profile_id: str, db_path: Path | None = None) -> None:
    while True:
        pending = get_pending_unresolved(profile_id, db_path)
        if not pending:
            print("Keine offenen unresolved_folders mehr.")
            return

        unresolved_id, folder_name, folder_level, occurrence_count, sample_path = pending[0]
        suggestion = suggest_action(folder_name)
        suggestion_hint = f"  (Vorschlag: {suggestion})" if suggestion else ""
        print(f"\n[level{folder_level}] '{folder_name}'  ({occurrence_count}x, z.B. {sample_path}){suggestion_hint}")
        print("  [a] Artist neu     [A] Artist bestehend (Suche)")
        print("  [p] Provider neu   [P] Provider bestehend (Suche)")
        print("  [c] Kategorie      [t] Trash")
        ignore_label = "Ignorieren (→ Collection-Name)" if folder_level == 2 else "Ignorieren"
        print(f"  [i] {ignore_label}     [q] Beenden")
        choice = input("> ").strip()

        if choice == "q":
            return

        if choice == "i":
            ignore_folder(unresolved_id, db_path)
            continue

        if choice == "c":
            set_category(unresolved_id, db_path)
            continue

        if choice == "t":
            set_trash(unresolved_id, db_path)
            continue

        if choice in ("a", "p"):
            kind = "artist" if choice == "a" else "provider"
            name = input(f"Canonical name für {kind} [{folder_name}]: ").strip() or folder_name
            collection_override = input("Collection für diesen Ordner (optional, Enter zum Überspringen): ").strip()
            _, conflict = assign_to_new_entity(unresolved_id, kind, name, db_path, collection_override or None)
            _print_conflict(conflict)
            continue

        if choice in ("A", "P"):
            kind = "artist" if choice == "A" else "provider"
            query = input("Suchbegriff: ").strip()
            matches = search_entities(kind, query, db_path)
            if not matches:
                print("Keine Treffer.")
                continue
            for i, (eid, cname) in enumerate(matches):
                print(f"  [{i}] {cname} ({eid})")
            idx = input("Auswahl (Index): ").strip()
            if not idx.isdigit() or int(idx) >= len(matches):
                print("Ungültige Auswahl.")
                continue
            entity_id = matches[int(idx)][0]
            collection_override = input("Collection für diesen Ordner (optional, Enter zum Überspringen): ").strip()
            conflict = assign_to_existing_entity(unresolved_id, kind, entity_id, db_path, collection_override or None)
            _print_conflict(conflict)
            continue

        print("Ungültige Eingabe.")
