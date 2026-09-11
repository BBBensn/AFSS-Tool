---
date_created: 2026-09-11 18:40:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 18:40:00
---

# v1.2.0 — artists.json/providers.json Sync-Lücke geschlossen (2026-09-11)
- **Bug gefunden und behoben**: "Artist neu"/"Provider neu" im Tag-UI hat nur in die SQLite-DB
  geschrieben, nie in `artists.json`/`providers.json` — dadurch waren neu angelegte Identitäten im
  Artist-Editor unsichtbar. Betraf **140 Artists und 2 Provider**, die während der `my_passport`-
  Sortierung entstanden sind
- Einmaliger Backfill (`afss sync-identities`) nachgeholt: alle 140+2 fehlenden Einträge mit ihren
  bekannten Aliases ergänzt, bestehende 81+13 Einträge unverändert gelassen (verifiziert)
- `assign_to_new_entity`/`assign_to_existing_entity` schreiben jetzt automatisch durch nach
  `artists.json`/`providers.json`, damit die Lücke nicht wieder auftritt
- Neuer Befehl `afss sync-identities --config-dir config` für künftige Fälle (z.B. falls das
  Tool auf einer Maschine ohne Config-Dir-Zugriff getaggt wurde)
- SQLite auf WAL-Modus + 30s Busy-Timeout umgestellt (behebt "database is locked" bei parallelen
  Dashboard-Aktionen, aufgetreten beim `plan`-Schritt für `my_passport`)
- Profil `my_passport` fertig sortiert und getaggt (74 % resolved, war zuletzt bei 5 %)

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten, damit die Fixes greifen
(Flask lädt Python-Codeänderungen nicht automatisch nach).
