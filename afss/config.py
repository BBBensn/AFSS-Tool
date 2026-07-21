import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def _require_yaml():
    if yaml is None:
        print("[ERROR] PyYAML fehlt, bitte `pip install pyyaml`")
        sys.exit(1)


def load_profiles(config_dir: Path) -> list[dict]:
    _require_yaml()
    path = Path(config_dir) / "legacy_profiles.yml"
    if not path.exists():
        raise FileNotFoundError(f"legacy_profiles.yml nicht gefunden: {path}")
    with path.open("r", encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"legacy_profiles.yml ist kein gültiges YAML: {exc}") from exc
    return data.get("profiles", [])


def get_profile(config_dir: Path, profile_id: str) -> dict:
    for p in load_profiles(config_dir):
        if p.get("id") == profile_id:
            return p
    raise ValueError(f"Profile nicht gefunden: {profile_id}")
