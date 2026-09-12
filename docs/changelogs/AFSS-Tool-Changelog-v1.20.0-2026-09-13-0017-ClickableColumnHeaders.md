---
date_created: 2026-09-13 00:17:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-13 00:17:00
---

# v1.20.0 — Sortier-Studio: Spalten-Header klickbar sortieren (2026-09-13)

- **Kopfzeile klickbar**: Klick auf eine Spaltenüberschrift (Datei, Artist, Studio, Collection,
  Provider, Status, Co-Artists, Titel-Override, Tags) sortiert wie in Tabellenprogrammen üblich,
  erneuter Klick auf dieselbe Spalte kehrt die Richtung um (▲/▼-Pfeil zeigt aktive Spalte +
  Richtung). Rein client-seitig, da alle Werte schon im DOM stehen - kein Server-Roundtrip nötig.
  Kollidiert nicht mit dem bestehenden "Sortieren"-Dropdown: die Spalten-Sortierung wirkt bewusst
  nur *innerhalb* jeder bestehenden Artist-/Collection-Gruppe, genau wie das Dropdown die
  Artist-Gruppierung nie aufbricht. Übersteht wie Filter/Scroll-Position einen Save.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
