---
date_created: 2026-09-12 21:26:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 21:26:00
---

# v1.19.0 — Sortier-Studio: "Alle Treffer auswählen" (2026-09-12)

- **Neuer Button "Alle Treffer auswählen"** unter dem Filterfeld: markiert mit einem Klick alle
  aktuell sichtbaren (gefilterten) Dateien auf einmal - unabhängig davon, in wie vielen
  verschiedenen Artist-/Collection-Gruppen sie liegen. Bisher musste jede Gruppe mit Treffern
  einzeln über ihre eigene Checkbox angehakt werden. Gedacht für den Workflow "im Dateinamen nach
  etwas suchen (z.B. einem Provider), alle Treffer markieren, dann z.B. Provider setzen".
  Berücksichtigt sowohl den Text-Filter als auch die Platten-Checkboxen in der `all`-Ansicht;
  gesperrte Artists bleiben wie gehabt ausgenommen.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
