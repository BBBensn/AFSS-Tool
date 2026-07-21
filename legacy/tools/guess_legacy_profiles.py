import argparse
import json
import os
from pathlib import Path
from collections import Counter, defaultdict

# --- Konfiguration ---

# Welche Endungen gelten als Video / Photo?
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def normalize_name(name: str) -> str:
    """Vereinfacht Provider-/Ordnernamen für Vergleiche."""
    import re

    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def load_provider_aliases(providers_path: Path) -> set[str]:
    """Liest providers.json und sammelt alle Aliases + Canonical-Namen."""
    if not providers_path.exists():
        print(f"[WARN] providers.json nicht gefunden unter {providers_path}")
        return set()

    data = json.loads(providers_path.read_text(encoding="utf-8"))
    aliases = set()

    # flexibel: data kann {"providers":[...]} oder eine Liste sein
    providers = data.get("providers", data if isinstance(data, list) else [])

    for p in providers:
        canon = p.get("canonical_name") or p.get("name") or ""
        if canon:
            aliases.add(normalize_name(canon))
        for alias in p.get("aliases", []):
            aliases.add(normalize_name(alias))

    return aliases


def classify_media_type(root: Path) -> str:
    """Bestimmt grob media_type: video / photo / mixed."""
    counts = Counter()
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            ext = Path(fn).suffix.lower()
            if ext in VIDEO_EXTS:
                counts["video"] += 1
            elif ext in PHOTO_EXTS:
                counts["photo"] += 1
        # nicht zu tief, wir wollen nur einen Eindruck
        # (Performance-Schutz bei großen Libs)
        if sum(counts.values()) > 500:
            break

    if not counts:
        return "mixed"

    if counts["video"] and counts["photo"]:
        return "mixed"
    if counts["video"]:
        return "video"
    if counts["photo"]:
        return "photo"
    return "mixed"


def scan_root(root: Path, provider_aliases: set[str], max_artists: int = 50):
    """
    Scannt eine Legacy-Root-Struktur:

    - Ebene 1: Artist-Ordner
    - Ebene 2: Provider-/Collection-Ordner
    """
    artist_dirs = [p for p in root.iterdir() if p.is_dir()]
    artist_dirs = sorted(artist_dirs, key=lambda p: p.name)[:max_artists]

    provider_folder_names = set()
    collection_folder_names = set()

    for artist_dir in artist_dirs:
        # Ebene 2
        for child in artist_dir.iterdir():
            if not child.is_dir():
                continue
            norm = normalize_name(child.name)
            if norm in provider_aliases:
                provider_folder_names.add(child.name)
            else:
                collection_folder_names.add(child.name)

    return {
        "artist_count_sample": len(artist_dirs),
        "provider_folder_names": sorted(provider_folder_names),
        "collection_folder_names": sorted(collection_folder_names),
    }


def build_yaml_profile(root: Path, media_type: str, scan_info: dict) -> str:
    """Erzeugt einen YAML-Block als String für dieses Root."""
    root_norm = normalize_name(str(root).replace(":", "").replace("\\", "_").replace("/", "_"))
    profile_id = f"legacy_auto_{root_norm or 'root'}"

    provider_examples = scan_info["provider_folder_names"][:10]
    collection_examples = scan_info["collection_folder_names"][:10]

    lines = []
    lines.append("version: 1")
    lines.append("")
    lines.append("profiles:")
    lines.append(f"  - id: {profile_id}")
    lines.append(f"    description: \"AUTO-GENERIERT: Legacy-Root {root}\"")
    lines.append("    enabled: false")
    lines.append("")
    lines.append(f"    root_path: \"{root}\"")
    lines.append(f"    media_type: \"{media_type}\"")
    lines.append("")
    lines.append("    artist_level:")
    lines.append("      depth: 1")
    lines.append("      source: \"folder_name\"")
    lines.append("")
    lines.append("    subfolder_rules:")
    lines.append("      - depth: 2")
    lines.append("        role: \"mixed\"")
    lines.append("        flatten: true")
    lines.append("        provider_from_folder: true")
    lines.append("        collection_from_folder: true")

    if provider_examples:
        lines.append("        provider_examples:")
        for name in provider_examples:
            lines.append(f"          - \"{name}\"")

    if collection_examples:
        lines.append("        collection_examples:")
        for name in collection_examples:
            lines.append(f"          - \"{name}\"")

    lines.append("")
    if media_type in {"video", "mixed"}:
        lines.append("    file_patterns:")
        lines.append("      - name: \"video_default\"")
        lines.append("        glob: \"*.mp4\"")
        lines.append("        title_from: \"filename_no_ext\"")
        lines.append("        artist_in_filename: false")
        lines.append("        provider_in_filename: false")
        lines.append("")
    else:
        lines.append("    file_patterns:")
        lines.append("      - name: \"photo_default\"")
        lines.append("        glob: \"*.jpg\"")
        lines.append("        title_from: \"filename_no_ext\"")
        lines.append("        artist_in_filename: false")
        lines.append("        provider_in_filename: false")
        lines.append("")

    lines.append("    flags:")
    lines.append("      treat_jpg_as_photos: true")
    lines.append("      mark_origin_as: \"legacy_auto_guess\"")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Auto-Guess von legacy_profiles.yml auf Basis eines Roots und providers.json"
    )
    parser.add_argument(
        "roots",
        nargs="+",
        help="Legacy-Root-Pfade (z. B. X:/legacy/videos)",
    )
    parser.add_argument(
        "--config-dir",
        default="config",
        help="Pfad zum Config-Verzeichnis (Standard: ./config)",
    )
    parser.add_argument(
        "--output",
        default="legacy_profiles.guessed.yml",
        help="Ausgabedatei (Standard: legacy_profiles.guessed.yml)",
    )
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    providers_path = config_dir / "providers.json"
    provider_aliases = load_provider_aliases(providers_path)

    if not provider_aliases:
        print("[WARN] Keine Provider-Aliases gefunden – provider_from_folder-Erkennung ist eingeschränkt.")

    yaml_blocks = []
    for root_str in args.roots:
        root = Path(root_str).expanduser()
        if not root.exists():
            print(f"[WARN] Root existiert nicht: {root}")
            continue

        media_type = classify_media_type(root)
        scan_info = scan_root(root, provider_aliases)
        yaml_block = build_yaml_profile(root, media_type, scan_info)
        yaml_blocks.append(yaml_block)

        print(f"[INFO] Root gescannt: {root}")
        print(f"       Sample Artists: {scan_info['artist_count_sample']}")
        print(f"       Provider-Folder: {scan_info['provider_folder_names']}")
        print(f"       Collection-Folder: {scan_info['collection_folder_names']}")
        print("")

    if not yaml_blocks:
        print("[INFO] Keine gültigen Roots gescannt. Keine Ausgabe erzeugt.")
        return

    out_path = Path(args.output)
    content = "\n".join(yaml_blocks)
    out_path.write_text(content, encoding="utf-8")
    print(f"[OK] Vorschlag in {out_path} geschrieben.")
    print("     Bitte manuell prüfen und nachschärfen, bevor du es als echtes legacy_profiles.yml verwendest.")


if __name__ == "__main__":
    main()
