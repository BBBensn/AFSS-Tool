---
date_created: 2026-09-12 10:04:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 10:04:00
---

# v1.14.0 — Sortier-Studio: Ursache für "Aktion fehlgeschlagen" gefunden, Artist-Spalte, Toolbox-Reihenfolge (2026-09-12)

- **Root Cause gefunden und behoben**: Dank des neuen Error-Handlers aus v1.13.0 kam endlich die
  echte Fehlermeldung durch: `413 Request Entity Too Large`. Flask begrenzt Formulardaten
  standardmäßig auf 500 KB (`MAX_FORM_MEMORY_SIZE`) - bei einer großen Auswahl über viele Dateien
  in der `all`-Ansicht (mehrere tausend `item_id`-Checkboxen in einem POST) wurde dieses Limit
  überschritten, jede Aktion schlug fehl. Da dieses Tool ausschließlich lokal für einen einzelnen
  Nutzer läuft, ist das Limit jetzt deaktiviert (`app.config["MAX_FORM_MEMORY_SIZE"] = None"`), in
  Dashboard- und Standalone-Sort-App. Mit einem Regressionstest (20.000 ausgewählte Dateien)
  abgesichert.
- **Neue Spalte "Artist"** in der Dateitabelle: zeigt pro Zeile den aktuell zugeordneten
  Artist-Namen (bisher nur über die Gruppenüberschrift sichtbar) - der einzige über die Toolbox
  gesetzte Parameter, der bisher nicht direkt in der Tabelle nachvollziehbar war. Unaufgelöste
  Dateien zeigen "(kein Artist zugeordnet)" farblich gedimmt.
- **Toolbox neu sortiert**: Ansicht enthält jetzt nur noch das Filterfeld; Reihenfolge ist jetzt
  Ansicht → Artist → Co-Artist → Provider → Collection → Status → Tags → Sortieren (neue eigene Box,
  inkl. Platten-Filter-Chips und "Alle zuklappen") → Verwaltung → Alles setzen.
- Grid-Spalten der Dateitabelle neu durchgezählt (jetzt 9 statt 8) und Kopfzeile/Datenzeilen exakt
  synchron gehalten, damit Spaltenüberschriften zuverlässig über den passenden Werten stehen.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
