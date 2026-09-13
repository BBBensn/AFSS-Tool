---
date_created: 2026-09-13 19:24:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-13 19:24:00
---

# v1.27.0 — Artist-Liste: Bugfixes + Auswahl wiederholen (2026-09-13)

- **Root Cause für "Kopfzeile fixieren funktioniert nicht" gefunden:** `overflow: hidden` auf der
  Tabelle selbst (nur zum Abrunden der Ecken gedacht) macht die Tabelle zum eigenen Scroll-Container
  und bricht `position: sticky` auf den `<th>`-Elementen dadurch in JEDEM Browser vollständig -
  nicht das erwartete Safari-spezifische `border-collapse`-Problem (das wurde vorsorglich trotzdem
  behoben, `border-collapse: separate` statt `collapse`). Fix: `overflow: hidden` entfernt, die
  Eckenrundung übernehmen jetzt gezielt die vier Eckzellen (`thead/tbody :first-child`/`:last-child`).
  Per Scroll-Test verifiziert (`getBoundingClientRect().top` bleibt exakt `0` beim Scrollen).
- **Alle sinnvollen `default_tags`-Felder jetzt als Spalte verfügbar** (24 statt bisher 6): Sex at
  Birth, Orientation, Geburtsdatum, Occupation, Bra/Boobs/Body Type, Hair/Eye Color, Height/Weight,
  Maße (Bust-Waist-Hips kombiniert), Artist Tags, Piercings, Priority, Aktiv seit/bis, Aktuell aktiv
  - weiterhin ein-/ausblendbar und gemerkt, neu hinzugekommene Spalten starten eingeklappt, damit
    Bestandsnutzer nicht plötzlich mit 24 sichtbaren Spalten dastehen. Formatierungslogik dafür in
    einer neuen `artist_column_values()`-Funktion (`store.py`) statt in duplizierten Jinja-Blöcken.
- **"Auswahl wiederholen"**: nach einer Bulk-Aktion wurden bisher alle Checkboxen zurückgesetzt -
  verhinderte es, z.B. erst Gender und danach noch Sexual Orientation für dieselbe Gruppe zu setzen,
  ohne die Auswahl jedes Mal neu zusammenzuklicken. Server merkt sich jetzt die zuletzt verwendete
  Auswahl (Flask-Session), ein Button direkt in der Erfolgsmeldung markiert exakt dieselben Artists
  erneut. Dasselbe Prinzip fürs Sortier-Studio ergänzt: neues Icon in der Verwaltungs-Box (Tooltip,
  kein Menü), merkt die letzte Datei-Auswahl clientseitig (sessionStorage) und stellt sie wieder her.
- **Header-Buttons (Lock/Spalten) jetzt rechtsbündig**: `.header-controls` hatte `margin-left: auto`
  auf dem bereits vollbreiten Flex-Container selbst stehen (wirkungslos) statt `justify-content:
  flex-end` - dadurch klebten die Icons links in der (durch die Aktionen-Spalte breiten) letzten
  Spalte statt rechts.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
