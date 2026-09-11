---
date_created: 2026-09-11 22:23:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 22:23:00
---

# v1.7.0 — Sortier-Studio: Zuordnungen zurücksetzen, Collections auflösen (2026-09-11)
- **Artist/Provider entfernen**: neue Bulk-Buttons, die `artist_id`/`provider_id` explizit auf
  NULL setzen (bisher gab es nur "Override aufheben", das nur das Auto-Resolve-Flag zurücksetzt,
  aber den aktuellen Wert nicht ändert)
- **Collection auflösen**: neuer Button direkt an jeder Collection-Gruppe ("Auflösen → Tag").
  Markiert alle Dateien der Collection automatisch, entfernt die Collection-Zuordnung (kein
  Unterordner mehr bei `apply`) und übernimmt den bisherigen Collection-Namen stattdessen als Tag.
  Für Ordner, die eigentlich eine Kategorie sind (z.B. "Solo") statt eine echte Shoot-Collection -
  Ergebnis: `Artist/` enthält danach nur noch echte Collections als Unterordner, alles andere liegt
  direkt im Artist-Ordner mit der Kategorie als Tag
- Neue Funktion `dissolve_collection()` in `afss/sort_studio.py`
- T7 als viertes Profil eingerichtet (`config/legacy_profiles.yml`, lokal/gitignored) - relevante
  Daten liegen unter `T7/other/`, nicht im Root; gescannt (1445 Dateien) und resolved (10,7 %,
  erwartungsgemäß niedrig da neue Platte mit noch unbekannten Artist-Namen)

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
