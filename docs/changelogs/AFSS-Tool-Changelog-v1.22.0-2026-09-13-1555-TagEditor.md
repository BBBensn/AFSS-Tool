---
date_created: 2026-09-13 15:55:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-13 15:55:00
---

# v1.22.0 — Neuer Tag-Editor (2026-09-13)

Zweiter von vier Schritten des Artist-/Tag-Editor-Ausbaus (siehe Plan
`ok-ich-bin-seit-humming-badger.md`).

- **Neue Seite `afss/tag_editor/`** (Route `/tags/`, auch im Dashboard registriert, plus
  eigenständiger Befehl `afss tags`): Übersichtstabelle aller im Sortier-Studio vergebenen Tags mit
  Nutzungszähler (Anzahl Dateien), Text-Filter, klickbar sortierbaren Spalten - bislang gab es dafür
  keine Übersicht, nur das Umbenennen-Panel im Sortier-Studio, das man nur "traf", wenn man schon
  wusste, dass ein Tag existiert.
- **Umbenennen/Zusammenführen/Entfernen direkt in der Liste**: pro Zeile ein Eingabefeld mit
  Autocomplete (neue Route `/tags/search`, wrapt `search_tags()`) - leeres Feld entfernt den Tag,
  ein vorhandener Zielname führt zusammen. Nutzt das bereits im Sortier-Studio gebaute
  `sort_studio.py::rename_tag()` direkt weiter, keine Logik-Duplikate. Neue Zähl-Funktion
  `list_all_tags()` daneben ergänzt.

**Noch offen** (Schritte 3-4): einheitliche Navigation über alle Seiten, leichter visueller
Politur-Pass.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
