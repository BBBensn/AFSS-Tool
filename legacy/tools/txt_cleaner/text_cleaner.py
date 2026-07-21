import argparse
import json
import os
from pathlib import Path


DEFAULT_MAPPING_PATH = Path("tools/mapping.json")


def load_mapping(mapping_path: Path):
    """
    Lädt das Mapping-File oder legt ein neues Grundgerüst an.
    Struktur:
    {
        "original_to_fake": { "Original": "TOKEN_0001", ... },
        "fake_to_original": { "TOKEN_0001": "Original", ... },
        "counter": 1,
        "whitelist": ["..."]
    }
    """
    if mapping_path.exists():
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
    else:
        data = {
            "original_to_fake": {},
            "fake_to_original": {},
            "counter": 1,
            "whitelist": []
        }
    # Fallbacks, falls altes Schema verwendet wurde
    data.setdefault("original_to_fake", {})
    data.setdefault("fake_to_original", {})
    data.setdefault("counter", 1)
    data.setdefault("whitelist", [])
    return data


def save_mapping(mapping_path: Path, data: dict):
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def generate_placeholder(counter: int) -> str:
    return f"TOKEN_{counter:04d}"


def apply_clean(text: str, mapping: dict) -> str:
    """
    Wendet bestehende original->fake-Mappings auf normalen Text an.
    Whitelist-Einträge werden NICHT ersetzt.
    Längere Phrasen zuerst, damit keine Teilstrings kaputtgehen.
    """
    original_to_fake = mapping["original_to_fake"]
    whitelist = set(mapping.get("whitelist", []))

    # Sortiere nach Länge, lange Strings zuerst
    items = sorted(original_to_fake.items(), key=lambda kv: len(kv[0]), reverse=True)

    for original, fake in items:
        if original in whitelist:
            continue
        if not original:
            continue
        text = text.replace(original, fake)
    return text


def apply_declean(text: str, mapping: dict) -> str:
    """
    Ersetzt Platzhalter wieder durch Originale.
    """
    fake_to_original = mapping["fake_to_original"]

    # Auch hier: längere Tokens zuerst
    items = sorted(fake_to_original.items(), key=lambda kv: len(kv[0]), reverse=True)

    for fake, original in items:
        if not fake:
            continue
        text = text.replace(fake, original)
    return text


def add_whitelist_interactive(mapping: dict):
    """
    Fragt nach zusätzlichen Whitelist-Phrasen (vor dem Run oder auf Wunsch danach).
    """
    current_whitelist = set(mapping.get("whitelist", []))

    print("\nOptional: Zusätzliche WHITELIST-Phrasen eingeben (werden nie ersetzt).")
    print("Mehrere Einträge mit Komma trennen, leer lassen zum Überspringen.")
    inp = input("Whitelist-Phrasen: ").strip()

    if not inp:
        return

    parts = [p.strip() for p in inp.split(",") if p.strip()]
    added = []
    for p in parts:
        if p not in current_whitelist:
            current_whitelist.add(p)
            added.append(p)

    mapping["whitelist"] = sorted(current_whitelist)
    if added:
        print(f"[INFO] Whitelist erweitert um: {added}")
    else:
        print("[INFO] Keine neuen Whitelist-Einträge hinzugefügt.")


def add_blacklist_interactive(cleaned_text: str, mapping: dict) -> str:
    """
    Nach dem ersten Clean-Run können zusätzliche Blacklist-Phrasen angegeben werden.
    Für jede Phrase wird ein neuer Platzhalter erzeugt, im Text ersetzt und in
    der mapping.json vermerkt.
    """
    original_to_fake = mapping["original_to_fake"]
    fake_to_original = mapping["fake_to_original"]
    whitelist = set(mapping.get("whitelist", []))
    counter = int(mapping.get("counter", 1))

    print("\nOptional: Zusätzliche BLACKLIST-Phrasen hinzufügen.")
    print("Diese Phrasen werden durch frische TOKEN_xxxx Platzhalter ersetzt.")
    print("Mehrere Einträge mit Komma trennen, leer lassen zum Überspringen.")
    inp = input("Blacklist-Phrasen: ").strip()

    if not inp:
        print("[INFO] Keine zusätzlichen Blacklist-Phrasen angegeben.")
        return cleaned_text

    parts = [p.strip() for p in inp.split(",") if p.strip()]
    if not parts:
        print("[INFO] Keine gültigen Phrasen erkannt.")
        return cleaned_text

    for phrase in parts:
        if phrase in whitelist:
            print(f"[WARN] Phrase '{phrase}' ist in der Whitelist – wird nicht ersetzt.")
            continue
        if phrase in original_to_fake:
            print(f"[INFO] Phrase '{phrase}' existiert bereits im Mapping, wird übersprungen.")
            continue

        placeholder = generate_placeholder(counter)
        counter += 1

        original_to_fake[phrase] = placeholder
        fake_to_original[placeholder] = phrase

        cleaned_text = cleaned_text.replace(phrase, placeholder)
        print(f"[INFO] Neue Mapping-Regel: '{phrase}' -> '{placeholder}'")

    mapping["counter"] = counter
    mapping["original_to_fake"] = original_to_fake
    mapping["fake_to_original"] = fake_to_original

    return cleaned_text


def main():
    parser = argparse.ArgumentParser(
        description="Text Cleaner/Decleaner für .txt und andere Text-Dateien (analog zum JSON-Cleaner)."
    )
    parser.add_argument(
        "mode",
        choices=["clean", "declean"],
        help="Betriebsmodus: clean (anonymisieren) oder declean (Original wiederherstellen).",
    )
    parser.add_argument(
        "path",
        help="Pfad zur Text-Datei, die verarbeitet werden soll.",
    )
    parser.add_argument(
        "--mapping",
        default=str(DEFAULT_MAPPING_PATH),
        help=f"Pfad zur mapping.json (Standard: {DEFAULT_MAPPING_PATH})",
    )
    args = parser.parse_args()

    mapping_path = Path(args.mapping)
    file_path = Path(args.path)

    if not file_path.exists():
        print(f"[ERROR] Datei nicht gefunden: {file_path}")
        return

    mapping = load_mapping(mapping_path)

    # Datei einlesen
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print("[ERROR] Konnte Datei nicht als UTF-8 lesen. Bitte Encoding prüfen.")
        return

    if args.mode == "clean":
        print(f"[INFO] Starte CLEAN für: {file_path}")

        # 1) Vorab-Whitelist erweitern (optional)
        add_whitelist_interactive(mapping)

        # 2) Bestehende Mappings anwenden
        cleaned = apply_clean(text, mapping)

        # 3) Zielpfad bestimmen
        out_path = file_path.with_name(file_path.stem + "_cleaned" + file_path.suffix)
        out_path.write_text(cleaned, encoding="utf-8")
        print(f"[OK] Vorläufige CLEAN-Datei geschrieben nach: {out_path}")

        # 4) Optionale neue Blacklist-Phrasen hinzufügen
        print("\nMöchtest du jetzt zusätzliche Blacklist-Phrasen hinzufügen und die Datei erneut anpassen?")
        yn = input("j/n: ").strip().lower()
        if yn == "j":
            cleaned = add_blacklist_interactive(cleaned, mapping)
            out_path.write_text(cleaned, encoding="utf-8")
            print(f"[OK] CLEAN-Datei mit neuen Blacklist-Phrasen aktualisiert: {out_path}")

        # 5) Optional: Whitelist nachträglich nochmal erweitern
        print("\nMöchtest du nachträglich noch weitere Whitelist-Phrasen hinzufügen?")
        yn_w = input("j/n: ").strip().lower()
        if yn_w == "j":
            add_whitelist_interactive(mapping)

        # Mapping speichern
        save_mapping(mapping_path, mapping)
        print(f"[OK] Mapping gespeichert unter: {mapping_path}")

    elif args.mode == "declean":
        print(f"[INFO] Starte DECLEAN für: {file_path}")

        # Bestehende Mappings rückwärts anwenden
        restored = apply_declean(text, mapping)

        out_path = file_path.with_name(file_path.stem + "_decleaned" + file_path.suffix)
        out_path.write_text(restored, encoding="utf-8")
        print(f"[OK] DECLEAN-Datei geschrieben nach: {out_path}")

        # Optional: auch hier Whitelist pflegbar (macht v. a. für spätere Clean-Runs Sinn)
        print("\nOptional: Whitelist jetzt noch erweitern (für künftige CLEAN-Läufe)?")
        yn_w = input("j/n: ").strip().lower()
        if yn_w == "j":
            add_whitelist_interactive(mapping)
            save_mapping(mapping_path, mapping)
            print(f"[OK] Mapping gespeichert unter: {mapping_path}")


if __name__ == "__main__":
    main()
