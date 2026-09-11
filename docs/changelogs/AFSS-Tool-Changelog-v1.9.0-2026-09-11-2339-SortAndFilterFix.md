---
date_created: 2026-09-11 23:39:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 23:39:00
---

# v1.9.0 — Sortier-Studio: Sortierbare Ansicht, Filter-Bug behoben (2026-09-11)
- **Bug behoben**: das Filterfeld hat seit der Spalten-Kopfzeile (v1.7.1) bei jeder Eingabe mit
  einem JS-Fehler abgebrochen (die Kopfzeile hatte kein `data-search`-Attribut) - Filtern hat
  dadurch faktisch gar nichts mehr gemacht, z.B. Suche nach `.mp4`/`.jpg` blieb wirkungslos. Jetzt
  behoben, inkl. Ursprungsordner (`rel_path`) in den durchsuchten Text aufgenommen
- **Treffer in eingeklappten Gruppen**: der Filter klappt jetzt automatisch die Artist-/
  Collection-Gruppen auf, in denen ein Treffer liegt - vorher blieben Treffer in eingeklappten
  Gruppen (ab 150 Dateien Standard) unsichtbar
- **Neue Sortierung**: Dropdown "Sortieren nach" in der Toolbar - Collection (Standard, wie
  bisher), Dateiname, Dateityp, Ursprungsordner. Bei allem außer "Collection" werden die
  Collection-Unterordner eines Artists aufgelöst und alle seine Dateien flach nach dem gewählten
  Kriterium sortiert angezeigt (Collection bleibt als eigene Spalte pro Zeile sichtbar) - damit
  lassen sich z.B. alle Fotos oder alle Dateien eines Ursprungsordners artistübergreifend über
  Collections hinweg im Zusammenhang sehen
- Neue Collection-Spalte in der Tabellenansicht (war vorher nur als Gruppen-Überschrift sichtbar)

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
