---
date_created: 2026-09-11 20:39:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 20:39:00
---

# v1.4.0 — Sortier-Studio: manuelle Bulk-Umsortierung (2026-09-11)
- Neue Dashboard-Ansicht "Sortieren" pro Profil: zeigt alle `media_items` gruppiert nach
  Artist → Collection als Liste (Checkbox-Mehrfachauswahl statt Drag & Drop, keine Thumbnails in
  dieser Version)
- Auswahl per Checkbox lässt sich in Bulk neu zuordnen: Artist (mit Live-Suche), Provider (mit
  Live-Suche), Collection (Freitext, leer = entfernen) — deckt auch "Collection aufteilen" ab
  (Teilmenge auswählen, neuen Collection-Namen setzen)
- Pro Datei ist der Titel überschreibbar (`title_override`), unabhängig vom Original-Dateinamen;
  `plan` verwendet ihn ab sofort bevorzugt gegenüber dem Dateinamen-Stem
- **Wichtig:** manuelle Zuordnungen werden ab jetzt dauerhaft respektiert — ein späterer
  `resolve`-Lauf überschreibt sie nicht mehr (neues `manual_override`-Flag auf `media_items`).
  "Override aufheben" macht das rückgängig, danach greift beim nächsten `resolve` wieder die
  automatische Alias-Logik
- Duplikate, die bereits über `dedupe` zum Löschen markiert sind, werden in der Liste ausgeblendet
- Neuer Standalone-Befehl `afss sort --profile <id>` (zusätzlich zur Dashboard-Integration)
- Keine Filetrees/Daten mussten für die Entwicklung geteilt werden — die komplette Ordnerstruktur
  lag durch `scan` bereits vollständig (alle Ebenen, nicht nur die für Matching genutzten) in
  `afss.db`

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten, damit "Sortieren" im
Dashboard erscheint.
