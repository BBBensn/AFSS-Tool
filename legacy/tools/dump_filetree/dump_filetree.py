import argparse
import os
import sys
from pathlib import Path

def dump_tree(path: Path, indent_level: int, output_file):
    indent = "  " * indent_level

    # Ordner und Dateien getrennt auflisten
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        return

    dirs = []
    files = []

    for name in entries:
        if name.startswith("."):  # versteckte Files ignorieren
            continue

        full_path = path / name
        if full_path.is_dir():
            dirs.append(name)
        else:
            files.append(name)

    # Ordner zuerst
    for d in dirs:
        print(f"{indent}{d}/", file=output_file)
        dump_tree(path / d, indent_level + 1, output_file)

    # Dann Dateien
    for f in files:
        print(f"{indent}{f}", file=output_file)


def main():
    parser = argparse.ArgumentParser(description="Sauberer Filetree-Dump für AFSS.")
    parser.add_argument("root", help="Root directory")
    parser.add_argument("-o", "--output", help="Output file", default=None)
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if not root.exists() or not root.is_dir():
        print(f"[ERROR] Ungültiger Pfad: {root}")
        return

    if args.output:
        with open(args.output, "w", encoding="utf-8") as out:
            print(f"{root.name}/", file=out)
            dump_tree(root, 1, out)
        print(f"[OK] Filetree gespeichert in {args.output}")
    else:
        print(f"{root.name}/")
        dump_tree(root, 1, output_file=sys.stdout)


if __name__ == "__main__":
    main()
