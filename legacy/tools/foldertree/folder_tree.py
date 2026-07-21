from pathlib import Path

def list_folders(root):
    root = Path(root)

    for path in sorted(root.rglob("*")):
        if path.is_dir():
            depth = len(path.relative_to(root).parts)
            indent = "  " * depth
            print(f"{indent}- {path.name}")

if __name__ == "__main__":
    root_path = input("Pfad zum Root-Ordner: ").strip('"')
    list_folders(root_path)
