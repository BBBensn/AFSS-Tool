import json
import os
import re
import argparse
from pathlib import Path
from hashlib import sha1

# Wenn mapping.json in ./config/ liegt:
MAPPING_FILE = "mapping.json"

def load_mapping():
    if not os.path.exists(MAPPING_FILE):
        return {"forward": {}, "reverse": {}}
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_mapping(mapping):
    os.makedirs(Path(MAPPING_FILE).parent, exist_ok=True)
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)

def generate_placeholder(original_word, mapping):
    """Erstellt eindeutigen Platzhalter, falls Word noch nicht existiert."""
    key = original_word.lower()

    if key in mapping["forward"]:
        return mapping["forward"][key]

    placeholder = "PH_" + sha1(original_word.encode("utf-8")).hexdigest()[:10].upper()

    mapping["forward"][key] = placeholder
    mapping["reverse"][placeholder] = original_word
    return placeholder

def clean_text(text, mapping):
    # existierende Wörter aus Mapping zuerst berücksichtigen
    token_pattern = r"[A-Za-z0-9_.\-]+"
    candidates = re.findall(token_pattern, text)

    for word in candidates:
        if len(word) < 3:
            continue
        key = word.lower()
        if key not in mapping["forward"]:
            generate_placeholder(word, mapping)

    # jetzt ersetzen
    for original, placeholder in mapping["forward"].items():
        regex = re.compile(re.escape(original), re.IGNORECASE)
        text = regex.sub(placeholder, text)

    return text

def declean_text(text, mapping):
    for placeholder, original in mapping["reverse"].items():
        text = text.replace(placeholder, original)
    return text

def prompt_additional_phrases(output_text, mapping):
    """
    Fragt optional nach zusätzlichen Phrasen, die anonymisiert werden sollen.
    Eingabe: kommasepariert, z.B.: phrase_1, 55 x, 500 km
    """
    print("\nOptional: zusätzliche Phrasen anonymisieren.")
    user_input = input(
        "Phrasen kommasepariert eingeben (oder einfach Enter für keine): "
    ).strip()

    if not user_input:
        return output_text  # nichts zusätzlich

    phrases = [p.strip() for p in user_input.split(",") if p.strip()]

    for phrase in phrases:
        placeholder = generate_placeholder(phrase, mapping)
        # exakter Replace, case-sensitiv – du bestimmst die Schreibweise
        output_text = output_text.replace(phrase, placeholder)
        print(f"  → '{phrase}' → {placeholder}")

    return output_text

def process_file(mode, input_path):
    mapping = load_mapping()
    input_path = Path(input_path)
    original_text = input_path.read_text(encoding="utf-8")

    if mode == "clean":
        output_text = clean_text(original_text, mapping)
        # Interaktive Zusatz-Phase
        output_text = prompt_additional_phrases(output_text, mapping)
        output_path = input_path.with_name(
            input_path.stem + "_cleaned" + input_path.suffix
        )

    elif mode == "declean":
        output_text = declean_text(original_text, mapping)
        output_path = input_path.with_name(
            input_path.stem + "_restored" + input_path.suffix
        )
    else:
        raise ValueError("Mode must be either 'clean' or 'declean'")

    output_path.write_text(output_text, encoding="utf-8")
    save_mapping(mapping)

    print(f"\n[OK] {mode} completed: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean/De-clean anonymization tool")
    parser.add_argument("mode", choices=["clean", "declean"], help="Operation mode")
    parser.add_argument("file", help="Path to file to process")
    args = parser.parse_args()

    process_file(args.mode, args.file)
