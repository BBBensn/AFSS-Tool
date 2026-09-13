---
date_created: 2026-09-13 16:12:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-13 16:12:00
---

# v1.24.0 — Visueller Politur-Pass (2026-09-13)

Vierter und letzter Schritt des Artist-/Tag-Editor-Ausbaus (siehe Plan
`ok-ich-bin-seit-humming-badger.md`) - "form over function" bleibt, aber die Form durfte etwas
schöner werden.

- Die im Sortier-Studio bereits verfeinerte Farbpalette (`--card-bg`, `--input-bg`, `--accent`,
  `--accent-soft`, `--border-hover`) auf Dashboard, Artist-Liste, Artist-Formular und Tag-Editor
  übertragen: Eingabefelder mit dezentem "inset"-Hintergrund, Tabellen mit abgerundeten Ecken und
  Kopfzeilen-Hintergrund, größere Radien auf Buttons/Feldern (5-6px statt 4-5px).
  Primäre Aktionen (Sortieren/Tag-Links im Dashboard, "+ Neuer Artist", "Speichern") in Akzentfarbe
  hervorgehoben - reine Farb-/Spacing-Anpassung, keine Struktur- oder Layout-Änderung.
- Dabei zwei CSS-Spezifitäts-Kollisionen gefunden und behoben: `a.btn`/`button[type=submit]`
  (Element+Klasse) schlugen `.btn-primary`/`.btn-danger` (nur Klasse) und überschrieben deren
  Akzent- bzw. Warnfarbe stillschweigend - behoben durch Erhöhen der Spezifität
  (`a.btn-primary`, `button.btn-danger`).

Damit ist der komplette vierteilige Ausbau (Autocomplete, Tag-Editor, einheitliche Navigation,
Politur) abgeschlossen.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
