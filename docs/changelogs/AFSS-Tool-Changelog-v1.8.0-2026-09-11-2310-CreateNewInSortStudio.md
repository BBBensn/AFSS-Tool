---
date_created: 2026-09-11 23:10:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 23:10:00
---

# v1.8.0 — Sortier-Studio: neue Artists/Provider direkt anlegen (2026-09-11)
- Neue Buttons "Neu anlegen & setzen" bei Artist und Provider, sowie "Neu anlegen & hinzufügen"
  beim Co-Artist-Feld: wenn die Suche keinen Treffer liefert, legt der eingetippte Name direkt
  einen neuen Eintrag an (in `artists.json`/`providers.json` **und** der DB) und weist ihn sofort
  der Auswahl zu - kein Umweg mehr über den Artist-Editor nötig
- Buttons sind deaktiviert, solange das Suchfeld leer ist oder ein bestehender Treffer aus der
  Autocomplete-Liste gewählt wurde (dann gewinnt der bestehende Eintrag, wie gewünscht)
- Bewusst ohne Dubletten-Prüfung gegen bestehende Aliase - mögliche Duplikate werden wie bei den
  Artists zuvor später über die Merge-Funktion im Artist-Editor bereinigt
- Neue Funktion `create_entity()` in `afss/sort_studio.py`
- `tagging.py`: `_load_json_store`/`_save_json_store` zu `load_json_store`/`save_json_store`
  gemacht (jetzt von zwei Modulen genutzt, daher öffentlich statt modul-intern)

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
