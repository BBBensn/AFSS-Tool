---
date_created: 2026-09-12 08:17:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 08:17:00
---

# v1.12.0 — Sortier-Studio: Bugfix "Aktion fehlgeschlagen", Toolbox-Redesign (2026-09-12)

- **Bugfix: Speichern schlug seit v1.11.0 fehl.** Die neuen `/sort/*`-Routen (AJAX-Swap) hatten
  keine eigene Fehlerbehandlung - ein serverseitiger Fehler landete als nichtssagender Flask-500
  (kein Traceback sichtbar, da das Dashboard mit `debug=False` läuft) und wurde im Frontend nur als
  generisches "Aktion fehlgeschlagen" gemeldet, ohne jede Ursache. `bulk`/`details`/
  `remove-co-artist`/`toggle-lock` fangen Fehler jetzt ab und zeigen die echte Fehlermeldung als
  Flash-Hinweis an (gleiches Muster wie `dashboard/app.py::run_action`) - eine künftige Ursache ist
  damit sofort sichtbar statt geraten werden zu müssen. Zusätzlich: ein rein client-seitiger Fehler
  beim Wiederaufbau der Seite nach einem erfolgreichen Speichern (State-Restore) wird nicht mehr
  fälschlich als gescheiterte Aktion gemeldet.
- **Toolbox aufgeräumt**: Felder sind jetzt in klar beschriftete Gruppen sortiert (Ansicht, Artist,
  Provider, Collection, Status, Co-Artist, Tags, Verwaltung), textlastige Buttons (Setzen/Entfernen/
  Neu anlegen & setzen) sind durch kompakte Icons ersetzt (Haken/Plus/X/Diskette/Undo/Flagge/Tag/
  Person+) mit Text als Hover-Tooltip. Icons sind inline SVG (keine externe Icon-Font/CDN - bleibt
  offline, wie der Rest des Tools). "Alles setzen" steht jetzt als letztes Element unten rechts in
  der Toolbox statt vorne links.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
