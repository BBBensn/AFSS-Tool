---
date_created: 2026-09-11 19:09:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 19:09:00
---

# v1.3.0 — Artist-Merge im Artist-Editor (2026-09-11)
- Neue Funktion in der Bearbeiten-Ansicht jedes Artists: "Mit anderem Artist zusammenführen" mit
  Live-Suchfeld über bestehende Artists (via `/artists/search`)
- Beim Merge: Name und Aliase des aufgelösten (doppelten) Eintrags werden automatisch als Alias
  beim Ziel-Artist eingetragen, zugeordnete `media_items` werden auf den Ziel-Artist umgehängt,
  der doppelte Eintrag wird danach aus `artists.json` und der DB entfernt — keine Leichen
- Funktioniert unabhängig davon, ob die Einträge nur in `artists.json`, nur in der DB oder in
  beidem existieren (z.B. wenn ein Duplikat nur über den Editor angelegt wurde und nie über das
  Tag-UI verwendet wurde)
- Alias-Konflikte (Name kollidiert mit einem Alias eines dritten Artists) brechen den Merge nicht
  ab, werden aber als Warnung angezeigt
- Neue Funktionen: `merge_entities()` in `afss/tagging.py`, `search_artists()` in
  `afss/artist_editor/store.py`

**Notwendiger Neustart:** laufende `afss dashboard`/`afss artists`-Session neu starten.
