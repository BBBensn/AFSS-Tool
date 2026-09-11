---
date_created: 2026-09-12 01:13:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 01:13:00
---

# v1.11.0 — Sortier-Studio: keine echte Navigation mehr, Artist-Lock (2026-09-12)
- **Kein Full-Page-Reload mehr**: bisher hat jede Aktion einen echten Redirect+Neuladen ausgelöst -
  auch mit dem in v1.10.0 nachgezogenen State-Restore blieb ein sichtbarer "Ruckler" (Seite baut
  sich neu auf). Jetzt rendert der Server die Seite direkt in derselben Response, das Frontend holt
  diese per `fetch()` und tauscht nur den Inhalt aus (`#app-root`) - keine echte Browser-Navigation,
  dadurch bleiben Scroll-Position, offene/zugeklappte Gruppen etc. ohne jeden Sprung erhalten.
  `sessionStorage` bleibt als Fallback für den seltenen Fall eines echten manuellen Reloads
- **Artist sperren** ("wie ein gesperrter Layer in Photoshop"): neuer 🔒/🔓-Button pro Artist-Zeile.
  Gesperrt heißt: bleibt dauerhaft zugeklappt (auch bei "Alle aufklappen" oder Treffern im Filter),
  seine Checkboxen sind deaktiviert (nicht auswählbar, nimmt nicht an Bulk-Aktionen teil). Dient als
  Fortschrittsmarker - "diesen Artist habe ich schon fertig sortiert". Sperrzustand ist global (über
  alle Profile hinweg) und übersteht Neustarts, da er in der DB gespeichert wird
  (`sort_studio_locks`)

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
