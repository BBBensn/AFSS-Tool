---
date_created: 2026-09-11 21:38:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 21:38:00
---

# v1.5.0 — Sortier-Studio: Papierkorb-Status, Tags, Co-Artists (2026-09-11)
- **Dateistatus** (`item_status`): Dateien können im Sortier-Studio als `trash` (Screenshots,
  Torrent-Müll etc.) oder `extra` (z.B. Behind-the-Scenes-Fotos, die man behalten aber nicht wie
  normale Clips einsortieren will) markiert werden. `trash` wird von `plan`/`apply` automatisch
  ausgeschlossen - nichts wird dabei gelöscht, das bleibt ein separater expliziter Schritt
- **Tags**: freies Textfeld pro Datei (`tags`, kommasepariert) plus Bulk-Aktion "Tags hinzufügen"
  für mehrere Dateien auf einmal (ergänzt, überschreibt keine bereits gesetzten individuellen Tags).
  Vorerst nur in der AFSS-DB getrackt, Jellyfin-Export (z.B. als .nfo) ist ein späterer Schritt
- **Co-Artists** (Coop/Feature-Videos): neue Verknüpfungstabelle `media_item_co_artists` für
  zusätzliche Artists neben dem Hauptartist. Der Hauptartist bestimmt weiterhin den Zielordner bei
  `apply` - Co-Artists sind eine zusätzliche Zuordnung, damit das Video später (nach Jellyfin-Export)
  auch bei Suche nach dem zweiten Artist auffindbar ist
- Neue Funktionen in `afss/sort_studio.py`: `set_item_status`, `save_tags`, `add_tags`,
  `add_co_artist`, `remove_co_artist`

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
