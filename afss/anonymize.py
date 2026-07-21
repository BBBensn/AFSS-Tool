import json
import re
from pathlib import Path

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./\\-]+")
BUILTIN_WHITELIST = {
    "true", "false", "null",
    "def", "class", "import", "from", "return", "if", "else", "elif",
    "for", "while", "in", "and", "or", "not",
}


def load_mapping(path: Path) -> dict:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {}
    data.setdefault("original_to_fake", {})
    data.setdefault("fake_to_original", {})
    data.setdefault("counter", 1)
    data.setdefault("whitelist", [])
    return data


def save_mapping(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _next_token(counter: int) -> str:
    return f"TOKEN_{counter:04d}"


def add_whitelist(mapping: dict, phrases: list[str]) -> None:
    current = set(mapping.get("whitelist", []))
    current.update(p for p in phrases if p)
    mapping["whitelist"] = sorted(current)


def auto_discover_tokens(text: str, mapping: dict) -> None:
    original_to_fake = mapping["original_to_fake"]
    fake_to_original = mapping["fake_to_original"]
    whitelist = set(mapping.get("whitelist", [])) | BUILTIN_WHITELIST
    counter = int(mapping.get("counter", 1))

    for token in sorted(set(TOKEN_PATTERN.findall(text))):
        if len(token) < 3 or token in whitelist or token in original_to_fake:
            continue
        fake = _next_token(counter)
        counter += 1
        original_to_fake[token] = fake
        fake_to_original[fake] = token

    mapping["counter"] = counter


def apply_clean(text: str, mapping: dict) -> str:
    whitelist = set(mapping.get("whitelist", [])) | BUILTIN_WHITELIST
    items = sorted(mapping["original_to_fake"].items(), key=lambda kv: len(kv[0]), reverse=True)
    for original, fake in items:
        if not original or original in whitelist:
            continue
        text = text.replace(original, fake)
    return text


def apply_declean(text: str, mapping: dict) -> str:
    items = sorted(mapping["fake_to_original"].items(), key=lambda kv: len(kv[0]), reverse=True)
    for fake, original in items:
        if fake:
            text = text.replace(fake, original)
    return text


def clean_file(input_path: Path, mapping_path: Path, extra_whitelist: list[str] | None = None) -> Path:
    mapping = load_mapping(mapping_path)
    if extra_whitelist:
        add_whitelist(mapping, extra_whitelist)

    text = input_path.read_text(encoding="utf-8")
    auto_discover_tokens(text, mapping)
    cleaned = apply_clean(text, mapping)

    out_path = input_path.with_name(input_path.stem + "_cleaned" + input_path.suffix)
    out_path.write_text(cleaned, encoding="utf-8")
    save_mapping(mapping_path, mapping)
    return out_path


def declean_file(input_path: Path, mapping_path: Path) -> Path:
    mapping = load_mapping(mapping_path)
    text = input_path.read_text(encoding="utf-8")
    restored = apply_declean(text, mapping)

    out_path = input_path.with_name(input_path.stem + "_restored" + input_path.suffix)
    out_path.write_text(restored, encoding="utf-8")
    return out_path


def _load_json_cleaner_format(path: Path) -> dict:
    """Legacy json_cleaner Format: {'forward': {lower_original: placeholder}, 'reverse': {placeholder: original}}."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    reverse = data.get("reverse", {})
    return {original: placeholder for placeholder, original in reverse.items()}


def _load_omni_format(path: Path) -> dict:
    """omni_cleaner/txt_cleaner Format: {'original_to_fake': {...}, ...}."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("original_to_fake", {})


def migrate_legacy_mappings(json_cleaner_path: Path, omni_cleaner_path: Path, output_path: Path) -> dict:
    """Führt beide Alt-Formate in EIN konsolidiertes mapping.json zusammen.

    omni_cleaner-Einträge haben Vorrang (granulareres Format). Konflikte
    (gleicher Original-String, unterschiedliches Token) werden aufgelistet,
    nicht stillschweigend überschrieben.
    """
    omni_originals = _load_omni_format(omni_cleaner_path)
    json_originals = _load_json_cleaner_format(json_cleaner_path)

    merged = load_mapping(output_path)
    conflicts = []
    imported = 0

    for source_name, originals in (("omni", omni_originals), ("json_cleaner", json_originals)):
        for original, fake in originals.items():
            existing_fake = merged["original_to_fake"].get(original)
            if existing_fake is not None and existing_fake != fake:
                conflicts.append(
                    {"original": original, "kept": existing_fake, "discarded": fake, "source": source_name}
                )
                continue
            if existing_fake is None:
                merged["original_to_fake"][original] = fake
                merged["fake_to_original"][fake] = original
                imported += 1

    save_mapping(output_path, merged)
    return {"imported": imported, "conflicts": conflicts}
