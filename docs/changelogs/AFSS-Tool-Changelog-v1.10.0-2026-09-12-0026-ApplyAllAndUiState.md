---
date_created: 2026-09-12 00:26:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 00:26:00
---

# v1.10.0 — Sortier-Studio: "Alles setzen" + Layout bleibt beim Speichern erhalten (2026-09-12)
- **Neuer "✓ Alles setzen"-Button**: Auswahl treffen, beliebig viele Felder ausfüllen (Artist,
  Provider, Collection, Status, Co-Artist, Tags - auch neue Artists/Provider "on the fly"), ein
  Klick wendet alle ausgefüllten Felder gleichzeitig an. Leere Felder werden dabei übersprungen,
  nicht als "löschen" interpretiert (anders als bei den einzelnen Buttons) - genau der beschriebene
  Workflow "Auswahl -> Artist, Collection, Status setzen -> alles setzen, fertig"
- Status-Auswahl hat jetzt "— nicht ändern —" als Standard, damit "Alles setzen" den Status nicht
  versehentlich zurücksetzt, wenn er einfach nur nicht angefasst werden sollte
- **Layout bleibt beim Speichern erhalten**: aufgeklappte/zugeklappte Artist- und
  Collection-Gruppen, der Filtertext und die Scroll-Position überleben jetzt einen Save (vorher
  fiel nach jeder Aktion alles auf den Server-Standard zurück - bei großen Profilen wirkte das wie
  "alles wieder zugeklappt, Chaos"). Technisch: Zustand wird vor jedem Speichern in
  `sessionStorage` gesichert und nach dem Neuladen wieder angewendet
- Die gewählte Sortierung (`?sort=...`) geht jetzt ebenfalls nicht mehr bei jedem Save verloren

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
