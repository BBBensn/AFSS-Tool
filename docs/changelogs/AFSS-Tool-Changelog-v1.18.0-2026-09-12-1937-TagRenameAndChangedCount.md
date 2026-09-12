---
date_created: 2026-09-12 19:37:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 19:37:00
---

# v1.18.0 — Sortier-Studio: Tag umbenennen/entfernen, "davon geändert"-Zähler (2026-09-12)

- **Tag global umbenennen oder entfernen**: neuer ⇄-Button in "Verwaltung" öffnet ein kleines Panel
  (Tag suchen, Ersetzen durch - beide mit Autocomplete aus bereits vergebenen Tags). Wirkt bewusst
  profilübergreifend auf ALLE Dateien mit exakt diesem Tag (case-sensitive), nicht nur die aktuelle
  Auswahl - gedacht zum Bereinigen versehentlicher Nah-Duplikate (z.B. "Fav" vs. "fav"). Leeres
  Ersetzen-Feld löscht den Tag ersatzlos. Landet er bereits im Ziel-Tag, wird er nicht doppelt
  eingefügt. Mit Bestätigungsdialog, da es (anders als sonst im Sortier-Studio) nicht auf die
  Auswahl beschränkt ist.
- **"Titel & Tags speichern" zeigt jetzt auch, wie viel sich wirklich geändert hat**: das Formular
  schickt immer den Wert jeder sichtbaren Zeile mit (nicht nur bearbeitete), z.B. alle ~1600 Dateien
  eines Profils - bisher stand nur "1600 Titel, 1600 Tag-Felder gespeichert", ohne erkennbar zu
  machen, ob dabei versehentlich eine falsche Zeile mitgeändert wurde. Die Meldung lautet jetzt z.B.
  "1600 Titel-Felder geprüft (1 geändert), 1600 Tag-Felder geprüft (0 geändert)".

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
