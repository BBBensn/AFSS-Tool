---
date_created: 2026-09-11 22:56:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 22:56:00
---

# v1.7.1 — Sortier-Studio: Performance-Fix + Spalten-Übersicht (2026-09-11)
- **Bug behoben**: Tippen in ein Textfeld ließ die Seite bei größeren Profilen (z.B. t7 mit 1445
  Dateien) einfrieren. Ursache: alle Artist-/Collection-Gruppen waren standardmäßig aufgeklappt,
  bei vielen kleinen Gruppen (z.B. hunderte unresolved Ordner) rendert der Browser dadurch tausende
  Zeilen gleichzeitig - jeder Tastendruck hat das gesamte Layout neu berechnet. Fix: ab 150
  Dateien starten Gruppen eingeklappt (Hinweistext erklärt das), außerdem wird das Filterfeld jetzt
  debounced (250ms) statt bei jedem Tastendruck sofort neu zu filtern
- **Bessere Übersicht**: Zeilen sind jetzt in klare Spalten aufgeteilt (Datei, Provider, Status,
  Co-Artists, Titel-Override, Tags) mit Kopfzeile und "—" für leere Felder, statt alles als
  Badges neben dem Dateinamen zusammenzuquetschen - auf einen Blick sichtbar, was pro Datei schon
  gesetzt ist und was fehlt
- Dateianzahl wird jetzt oben angezeigt

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
