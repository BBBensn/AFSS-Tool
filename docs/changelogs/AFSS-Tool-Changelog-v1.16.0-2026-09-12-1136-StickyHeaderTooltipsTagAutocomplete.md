---
date_created: 2026-09-12 11:36:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 11:36:00
---

# v1.16.0 — Sortier-Studio: fixierbare Kopfzeile, lesbare Titel/Tags, Tag-Autocomplete (2026-09-12)

- **Kopfzeile fixierbar**: neuer 🔒/🔓-Toggle-Button ganz links in der Tabellen-Kopfzeile. Aktiviert,
  bleibt die Kopfzeile beim Scrollen direkt unter der (ebenfalls fixierten) Toolbar stehen, nur die
  Dateizeilen scrollen darunter weg. Der Offset wird automatisch an die aktuelle Toolbar-Höhe
  angepasst (die sich je nach Fensterbreite ändert, weil die Toolbox-Gruppen unterschiedlich
  umbrechen). Einstellung wird über `localStorage` gemerkt.
- **Titel-Override/Tags-Felder jetzt mit vollständigem Text als Hover-Tooltip**: die Felder in der
  Tabelle sind schmal und zeigen langen Text abgeschnitten - ein nativer Tooltip (title-Attribut)
  zeigt jetzt beim Hovern den kompletten, auch live während der Eingabe aktuellen Wert.
- **Autocomplete für Tags**: neue Funktion `search_tags()` durchsucht alle bereits vergebenen Tags
  (dedupliziert aus der kommaseparierten Freitext-Spalte) und liefert sie als Dropdown-Vorschläge -
  sowohl im Tags-Feld der Toolbox als auch in jedem einzelnen Tags-Feld der Tabelle. Da Tags reiner
  Freitext sind (keine eigene Tabelle wie Artists/Providers), gibt es keinen separaten
  "Neu anlegen"-Schritt - ein neuer Tag lässt sich weiterhin einfach eintippen, das Dropdown dient
  nur dazu, versehentliche Nah-Duplikate zu vermeiden (z.B. "fav" statt vorhandenem "Favorite").
  Autocomplete für Artist/Provider/Co-Artist gab es schon seit v1.4.1/v1.8.0.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
