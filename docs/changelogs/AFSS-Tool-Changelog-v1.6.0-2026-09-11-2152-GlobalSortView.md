---
date_created: 2026-09-11 21:52:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 21:52:00
---

# v1.6.0 — Sortier-Studio: profilübergreifende Ansicht (2026-09-11)
- `afss/sort_studio.py::get_profile_tree` unterstützt jetzt `profile_id="all"` (gleiche Konvention
  wie `dedupe_profile`/`apply_dedupe`) - zeigt alle Profile gemeinsam gruppiert nach Artist an
- Dadurch werden Artists, die über mehrere Platten verteilt sind, in **einer** Gruppe
  zusammengeführt statt getrennt pro Profil - Collections lassen sich so vollständig auflösen,
  ohne dass echte Dateien vorher manuell auf eine Platte umkopiert werden müssen
- Jede Datei zeigt in der globalen Ansicht ein Herkunfts-Badge (Profil-ID); Toolbar bekommt
  Checkbox-Filter pro Platte (rein clientseitig, kein Server-Roundtrip)
- Neuer Dashboard-Link "Alle Profile sortieren"
- `apply` bleibt weiterhin pro Profil (kopiert ja von der jeweiligen Quelle) - nur die
  Sortier-Entscheidung selbst trifft man jetzt einmal global

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
