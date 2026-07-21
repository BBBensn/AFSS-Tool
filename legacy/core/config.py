from pathlib import Path
import json
import sys

try:
    import yaml
except Exception:  # pragma: no cover - runtime guard for missing dependency
    yaml = None


def _read_json(path: Path) -> dict:
    if not path.exists():
        print(f"[WARN] JSON file not found: {path}")
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:
        print(f"[ERROR] Failed to read JSON {path}: {e}")
        return {}


def _read_yaml(path: Path) -> dict:
    if yaml is None:
        print("[ERROR] PyYAML fehlt, bitte `pip install pyyaml`")
        sys.exit(1)

    if not path.exists():
        print(f"[WARN] YAML file not found: {path}")
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception as e:
        print(f"[ERROR] Failed to read YAML {path}: {e}")
        return {}


def load_artists(path: Path) -> dict:
    """Load artists JSON and return parsed dict (or empty dict)."""
    return _read_json(Path(path))


def load_providers(path: Path) -> dict:
    """Load providers JSON and return parsed dict (or empty dict)."""
    return _read_json(Path(path))


def load_legacy_profiles(path: Path) -> dict:
    """Load legacy_profiles YAML and return parsed dict (or empty dict).

    Exits with a clear message when PyYAML is missing.
    """
    return _read_yaml(Path(path))
