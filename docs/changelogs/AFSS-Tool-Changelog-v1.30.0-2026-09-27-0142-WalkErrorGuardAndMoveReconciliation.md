---
date_created: 2026-09-27 01:42:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-27 01:42:00
---

# v1.30.0 — Zweiter kritischer Scan-Bug + Move-Erkennung (2026-09-27)

- **Root Cause für "haufenweise Dateien fälschlich als fehlend markiert" gefunden:** `os.walk()`
  schluckt Lese-Fehler pro Verzeichnis standardmäßig (`onerror=None`) - eine kurz hakende USB/SMB-
  Verbindung während eines Scans hätte einen ganzen, weiterhin vorhandenen Unterordner
  stillschweigend übersprungen. In Kombination mit der `missing_since`-Markierung aus v1.29.0 hätte
  das echte, unveränderte Dateien fälschlich als "fehlend" markiert - ohne jede Fehlermeldung.
  Analyse der echten DB zeigte: 0 Dateiname+Größe-Überschneidungen zwischen den 88 (`untitled`)
  bzw. 1521 (`my_passport`) als fehlend markierten Dateien und allem sonst im Profil (auch
  profilübergreifend) - beide betroffenen Platten sind aktuell nicht gemountet, ein klarer Hinweis
  auf Verbindungsprobleme während des ursprünglichen Scans, nicht auf echtes Löschen/Verschieben.
- **Fix:** `scan_profile()` übergibt jetzt einen `onerror`-Handler an `os.walk()` und sammelt
  aufgetretene Lese-Fehler. Gab es welche, wird die `missing_since`-Markierung für diesen Lauf
  komplett übersprungen (lieber keine neue Markierung als eine potenziell falsche) - sichtbar per
  klarer Warnung in CLI (`afss scan`) und Dashboard-Flash-Message.
- **Neu: `find_moved_file_matches()` / `apply_moved_file_matches()`** (`afss/scan.py`) + CLI-Befehl
  `afss reconcile-missing --profile <p> [--apply]` - findet unter den echten "fehlend"-Fällen (z.B.
  nach einer manuellen Ordner-Umbenennung beim Sortieren) eindeutige 1:1-Treffer per Dateiname+
  Dateigröße und führt sie zusammen: die weiterhin vorhandene Datei behält ihre eigene `id` (Co-
  Artists/Dedupe-Referenzen bleiben intakt) und wird nur um Felder ergänzt, die sie selbst noch
  NICHT gesetzt hat (nichts wird überschrieben). Mehrdeutige Fälle (z.B. gleich große, generische
  Dateinamen wie `001.jpg` in unabhängigen Ordnern) werden bewusst NICHT automatisch zusammengeführt.
  Ohne `--apply` reiner Trockenlauf (wie bei `dedupe`/`plan`).

**Wichtig für den Nutzer:** die aktuellen `missing_since`-Zahlen (88/1521) stammen von Scans VOR
diesem Fix und sind daher nicht vertrauenswürdig - beide Platten sauber mounten, mit dem neuen Code
neu scannen (meldet jetzt klar, falls wieder Lese-Fehler auftreten), danach `afss reconcile-missing`
laufen lassen und erst dann den verbleibenden `missing_total` als echten Stand betrachten.
