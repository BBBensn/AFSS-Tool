import argparse
import json
from pathlib import Path
import re

MAPPING_PATH_DEFAULT = Path("tools/mapping.json")

# -----------------------------
# Mapping-Handling
# -----------------------------

def load_mapping(path: Path) -> dict:
    """
    Struktur mapping.json:
    {
      "original_to_fake": { "Original": "TOKEN_0001", ... },
      "fake_to_original": { "TOKEN_0001": "Original", ... },
      "counter": 1,
      "whitelist": ["..."]
    }
    """
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {
            "original_to_fake": {},
            "fake_to_original": {},
            "counter": 1,
            "whitelist": []
        }

    # Fallbacks für ältere Versionen
    data.setdefault("original_to_fake", {})
    data.setdefault("fake_to_original", {})
    data.setdefault("counter", 1)
    data.setdefault("whitelist", [])

    return data


def save_mapping(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def next_token(counter: int) -> str:
    return f"TOKEN_{counter:04d}"


# -----------------------------
# Auto-Tokenisierung
# -----------------------------

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./\\-]+")

# Optionale „Hard-Whitelist“ für offensichtliche Standardbegriffe
BUILTIN_WHITELIST = {
    "true", "false", "null",
    "def", "class", "import", "from", "return", "if", "else", "elif",
    "for", "while", "in", "and", "or", "not",
    # kannst du nach Bedarf erweitern
}


def auto_discover_tokens(text: str, mapping: dict) -> None:
    """
    Sucht alle „Tokens“ im Text und legt für neue Tokens Mapping-Einträge an,
    sofern sie nicht in der Whitelist stehen.
    """
    original_to_fake = mapping["original_to_fake"]
    fake_to_original = mapping["fake_to_original"]
    whitelist = set(mapping.get("whitelist", [])) | BUILTIN_WHITELIST
    counter = int(mapping.get("counter", 1))

    candidates = set(TOKEN_PATTERN.findall(text))

    for token in candidates:
        if len(token) < 3:
            continue
        if token in whitelist:
            continue
        if token in original_to_fake:
            continue

        fake = next_token(counter)
        counter += 1

        original_to_fake[token] = fake
        fake_to_original[fake] = token

    mapping["counter"] = counter
    mapping["original_to_fake"] = original_to_fake
    mapping["fake_to_original"] = fake_to_original


# -----------------------------
# Clean / Declean
# -----------------------------

def apply_clean(text: str, mapping: dict) -> str:
    """
    Wendet original->fake-Mappings auf Text an.
    Längere Originalstrings zuerst, damit Teilstrings nicht kaputt gehen.
    """
    original_to_fake = mapping["original_to_fake"]
    whitelist = set(mapping.get("whitelist", [])) | BUILTIN_WHITELIST

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
    items = sorted(fake_to_original.items(), key=lambda kv: len(kv[0]), reverse=True)

    for fake, original in items:
        if not fake:
            continue
        text = text.replace(fake, original)

    return text


# -----------------------------
# Interaktive Whitelist / Blacklist
# -----------------------------

def interactive_add_whitelist(mapping: dict) -> None:
    current = set(mapping.get("whitelist", []))

    print("\nOptional: zusätzliche WHITELIST-Phrasen (werden NIE ersetzt).")
    print("Mehrere Einträge mit Komma trennen, leer lassen zum Überspringen.")
    inp = input("Whitelist-Phrasen: ").strip()

    if not inp:
        return

    for part in [p.strip() for p in inp.split(",") if p.strip()]:
        if part not in current:
            current.add(part)

    mapping["whitelist"] = sorted(current)
    print(f"[INFO] Whitelist jetzt: {mapping['whitelist']}")


def interactive_add_blacklist(text: str, mapping: dict) -> str:
    original_to_fake = mapping["original_to_fake"]
    fake_to_original = mapping["fake_to_original"]
    whitelist = set(mapping.get("whitelist", [])) | BUILTIN_WHITELIST
    counter = int(mapping.get("counter", 1))

    print("\nOptional: zusätzliche BLACKLIST-Phrasen (werden JETZT anonymisiert).")
    print("Mehrere Einträge mit Komma trennen, leer lassen zum Überspringen.")
    inp = input("Blacklist-Phrasen: ").strip()

    if not inp:
        return text

    for phrase in [p.strip() for p in inp.split(",") if p.strip()]:
        if phrase in whitelist:
            print(f"[WARN] '{phrase}' steht auf der Whitelist – wird nicht ersetzt.")
            continue
        if phrase in original_to_fake:
            print(f"[INFO] '{phrase}' existiert bereits im Mapping, wird übersprungen.")
            continue

        fake = next_token(counter)
        counter += 1

        original_to_fake[phrase] = fake
        fake_to_original[fake] = phrase

        text = text.replace(phrase, fake)
        print(f"[MAP] '{phrase}' → {fake}")

    mapping["counter"] = counter
    mapping["original_to_fake"] = original_to_fake
    mapping["fake_to_original"] = fake_to_original
    return text


# -----------------------------
# Main
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AFSS Cleaner: anonymisiert beliebige Textdateien (JSON/TXT/etc.) mit gemeinsamem Mapping."
    )
    parser.add_argument("mode", choices=["clean", "declean"],
                        help="clean = anonymisieren, declean = wiederherstellen")
    parser.add_argument("file", help="Pfad zur zu verarbeitenden Datei")
    parser.add_argument("--mapping", default=str(MAPPING_PATH_DEFAULT),
                        help=f"Pfad zu mapping.json (Default: {MAPPING_PATH_DEFAULT})")

    args = parser.parse_args()

    file_path = Path(args.file)
    mapping_path = Path(args.mapping)

    if not file_path.exists():
        print(f"[ERROR] Datei nicht gefunden: {file_path}")
        return

    mapping = load_mapping(mapping_path)

    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print("[ERROR] Datei ist nicht UTF-8-lesbar.")
        return

    if args.mode == "clean":
        print(f"[INFO] CLEAN für {file_path}")

        # 1) Whitelist vorab
        interactive_add_whitelist(mapping)

        # 2) Auto-Tokenisierung (neue Tokens auf Basis des Textes)
        auto_discover_tokens(text, mapping)

        # 3) Anwenden der Regeln
        cleaned = apply_clean(text, mapping)

        # 4) Datei schreiben
        out_path = file_path.with_name(file_path.stem + "_cleaned" + file_path.suffix)
        out_path.write_text(cleaned, encoding="utf-8")
        print(f"[OK] Vorläufige CLEAN-Datei: {out_path}")

        # 5) Optional: zusätzliche Blacklist-Phrasen
        print("\nZusätzliche Blacklist-Phrasen anwenden? (j/n)")
        if input("> ").strip().lower() == "j":
            cleaned = interactive_add_blacklist(cleaned, mapping)
            out_path.write_text(cleaned, encoding="utf-8")
            print(f"[OK] CLEAN-Datei aktualisiert: {out_path}")

        # 6) Optional Whitelist nachträglich erweitern
        print("\nWeitere Whitelist-Phrasen ergänzen? (j/n)")
        if input("> ").strip().lower() == "j":
            interactive_add_whitelist(mapping)

        save_mapping(mapping_path, mapping)
        print(f"[OK] Mapping gespeichert: {mapping_path}")

    else:  # declean
        print(f"[INFO] DECLEAN für {file_path}")
        restored = apply_declean(text, mapping)
        out_path = file_path.with_name(file_path.stem + "_decleaned" + file_path.suffix)
        out_path.write_text(restored, encoding="utf-8")
        print(f"[OK] DECLEAN-Datei: {out_path}")

        print("\nWhitelist jetzt noch pflegen (für zukünftige CLEAN-Läufe)? (j/n)")
        if input("> ").strip().lower() == "j":
            interactive_add_whitelist(mapping)
            save_mapping(mapping_path, mapping)
            print(f"[OK] Mapping gespeichert: {mapping_path}")


if __name__ == "__main__":
    main()
