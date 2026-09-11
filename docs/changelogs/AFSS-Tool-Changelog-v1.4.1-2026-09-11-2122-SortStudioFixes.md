---
date_created: 2026-09-11 21:22:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 21:22:00
---

# v1.4.1 — Sortier-Studio: Such-Bug + Bedienkomfort (2026-09-11)
- **Bug gefunden und behoben**: Artists, die nur über den Artist-Editor angelegt/bearbeitet wurden
  (nicht über die Tag-Queue), landeten ausschließlich in `artists.json`, nie in der SQLite-DB -
  Sortier-Studios Suche fragt aber die DB ab und fand sie deshalb nicht ("Melanie" als konkretes
  Beispiel; betraf **38 von 183 Artists**). Ursache: `artist_editor`s `save()`-Route schrieb bisher
  nur JSON, nie die DB (Gegenstück zur v1.2.0-Lücke, die die andere Richtung schon geschlossen hat)
- `save()` synct jetzt bei jedem Speichern auch die DB nach (`sync_artist_to_db`), inkl. sicherer
  Referenz-Umhängung falls die ID geändert wird
- Sortier-Studios Suche fragt jetzt direkt `artists.json`/`providers.json` ab statt die DB - das ist
  die verlässlichere Oberliste; `bulk_update` legt einen bisher nur-in-JSON existierenden Artist/
  Provider bei Zuweisung automatisch in der DB an (FK-sicher)
- Einmaliger Re-Import (`migrate_legacy_json`) auf die echten Daten angewendet, um die bereits
  entstandene Lücke zu schließen (183/183 Artists jetzt auch in der DB); dabei sind **12
  Alias-Konflikte** aufgefallen (z.B. `dirtygardengirl`/`artist_donna_flower`,
  `sageavery`/`artist_freakslutsage`, `candice`/`artist_kandice`,
  `bettyparlour`/`artist_sweetbettyparlour`) - vermutlich weitere, noch nicht gemergte Duplikate,
  lohnt sich per Artist-Merge (v1.3.0) nachzuziehen
- Sortier-Studio: "Alle zuklappen/aufklappen"-Button, Checkbox zum Markieren aller Dateien
  innerhalb eines Artist-/Collection-Blocks, Shift-Klick für Bereichsauswahl zwischen zwei Checkboxen

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
