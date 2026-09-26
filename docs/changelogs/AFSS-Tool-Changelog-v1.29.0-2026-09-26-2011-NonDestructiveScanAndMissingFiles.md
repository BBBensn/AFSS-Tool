---
date_created: 2026-09-26 20:11:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-26 20:11:00
---

# v1.29.0 — Kritischer Bugfix: Rescan löschte alle Tags (2026-09-26)

- **Root Cause:** `scan_profile()` hat bei JEDEM Lauf zuerst `DELETE FROM media_items WHERE
  profile_id = ?` ausgeführt und danach alle gefundenen Dateien komplett neu eingefügt - auch für
  Dateien, die sich seit dem letzten Scan gar nicht geändert hatten. Ein simples Rescan (z.B. um
  neu hinzugekommene Clips zu erfassen) hätte damit **jegliche im Sortier-Studio gesetzte Zuordnung
  fürs gesamte Profil gelöscht**: Artist/Provider/Studio, Tags, Titel-Override, Status, manuelle
  Sperren, Co-Artists - der bestehende Test `test_scan_is_idempotent` hat das nicht aufgedeckt, weil
  er nur die Zeilenzahl prüft, nicht ob Tagging-Daten erhalten bleiben. Zusätzlicher Nebeneffekt: da
  jede neu eingefügte Zeile eine neue `id` bekam, wurden `media_item_co_artists`/
  `dedupe_group_members` (beide referenzieren die alte `id`) bei jedem Rescan verwaist.
- **Fix:** `scan_profile()` macht jetzt einen Upsert nach `(profile_id, rel_path)` (bereits als
  UNIQUE-Constraint vorhanden). Eine bekannte Datei bekommt nur ihre dateisystem-abgeleiteten Spalten
  aufgefrischt (Pfad/Größe/mtime/Ordnerebenen) - alle Tagging-Spalten bleiben unangetastet, die `id`
  bleibt stabil. Neue Dateien werden ganz normal ergänzt.
- **Neu: Dateien, die verschwunden sind, werden nicht mehr gelöscht, sondern markiert.** Neue Spalte
  `media_items.missing_since` - wird beim ersten Nichtmehr-Finden gesetzt (z.B. Platte kurz nicht
  gemountet, Ordner umbenannt) und automatisch wieder gelöscht, sobald die Datei erneut gefunden
  wird. Wiederholte Scans einer weiterhin fehlenden Datei verschieben den Zeitpunkt nicht nach vorn.
- **Sichtbar gemacht, wie gewünscht:** Dashboard zeigt pro Profil "⚠ N Datei(en) auf der Platte nicht
  gefunden", falls vorhanden; Sortier-Studio zeigt eine "⚠ fehlt"-Badge direkt an der betroffenen
  Zeile (Tooltip mit Zeitpunkt). `afss scan` (CLI) gibt neu/insgesamt fehlende Dateien mit aus.
- Migration ist rein additiv (nur eine neue Spalte, `ALTER TABLE ... ADD COLUMN`) - gegen eine Kopie
  der echten `afss.db` (16.021 Zeilen, 15.925 bereits getaggt) getestet, keine bestehenden Daten
  angerührt.

**Sicherheitshinweis für den Nutzer:** dieser Fix behebt einen echten Datenverlust-Bug - vor diesem
Fix hätte ein Rescan eines bereits getaggten Profils die gesamte manuelle Tagging-Arbeit für dieses
Profil gelöscht. Ein Rescan ist ab jetzt sicher additiv.
