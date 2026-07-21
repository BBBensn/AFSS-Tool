from afss.normalize import normalize_name

# Bekannte Datenmüll-/System-Ordner (Windows-Papierkorb, Spotlight-Index, ...).
# Versteckte Ordner (Name beginnt mit ".") werden separat in scan.py behandelt.
TRASH_NAMES = {
    normalize_name(n)
    for n in (
        "$RECYCLE.BIN",
        "System Volume Information",
        ".Spotlight-V100",
        ".fseventsd",
        ".Trashes",
        ".directory",
        ".TemporaryItems",
        "found.000",
    )
}

# Generische Kategorie-Wörter, die in vielen Sammlungen als Sammelordner
# vorkommen (Ordnername, nicht Dateiendung) - bewusst allgemein gehalten.
CATEGORY_HINTS = {
    normalize_name(n)
    for n in (
        "Chat",
        "Pics",
        "Photos",
        "Pictures",
        "Videos",
        "Video",
        "Wallpaper",
        "Wallpapers",
        "Screenshots",
        "Screenlists",
        "Misc",
        "Other",
        "Random",
        "Mix",
        "Mixed",
        "Unsorted",
        "Various",
        "Extras",
        "Bonus",
        "Clips",
        "Trailers",
        "Previews",
        "Sets",
        "Collections",
        "Gifs",
        "Memes",
        "Sorted",
        "Unsorted_new",
        "New",
        "Old",
        "Archive",
    )
}


def suggest_action(folder_name: str) -> str | None:
    """Best-effort Vorschlag für einen unresolved-Ordner: 'trash', 'category' oder None
    (keine sichere Vermutung - z.B. bei Namen, die wie Personen/Handles aussehen,
    wird bewusst NICHTS vorgeschlagen, das bleibt eine manuelle Entscheidung)."""
    norm = normalize_name(folder_name)
    if not norm:
        return None
    if norm in TRASH_NAMES:
        return "trash"
    if norm in CATEGORY_HINTS:
        return "category"
    return None
