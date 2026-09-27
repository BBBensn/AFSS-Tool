---
date_created: 2026-09-27 07:15:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-27 07:15:00
---

# v1.31.1 — Zwei Windows-Kompatibilitäts-Bugfixes (2026-09-27)

Gefunden beim ersten Windows-Scan der vier Mac-getaggten Platten auf einem neu eingerichteten
Windows-PC (siehe `docs/changelogs/PC-Report-2026-09-27-WindowsSetupUndBugfixes.md` für den vollen
Bericht).

- **NFD/NFC-Pfad-Mismatch:** macOS (APFS/HFS+) speichert Dateinamen mit Umlauten/Akzenten/
  kyrillischen Zeichen zerlegt (NFD), Windows liefert dieselben Namen bei `os.walk()` zusammengesetzt
  (NFC) - optisch identisch, als String aber unterschiedlich. Der Upsert-Unique-Key
  `(profile_id, rel_path)` in `scan.py` hat das nicht erkannt: eine vom Mac bereits getaggte Zeile
  wurde fälschlich als "fehlend" markiert, eine neue leere Zeile für dieselbe physische Datei kam
  dazu. `scan.py` normalisiert `rel_path`/`filename` jetzt konsequent auf NFC (nur die Vergleichs-/
  Identitätsspalten - `path`, der reale Dateisystem-Zugriffspfad, bleibt unverändert).
  156 davon betroffene, bereits verwaiste Zeilen (untitled: 3, elements: 7, my_passport: 146) wurden
  per Einmal-Skript zusammengeführt (Tagging-Daten zurück auf die sichtbare Zeile, Referenzen in
  `media_item_co_artists`/`dedupe_group_members`/`media_technical_info` umgehängt, 0 verbleibende
  Duplikate verifiziert).
- **Ungültige NTFS-Erstellungszeit killt Dateigröße mit:** `st_ctime` liefert unter Windows für viele
  Dateien einen FILETIME-Nullwert-Sentinel (Jahr 1601) - `datetime.fromtimestamp()` wirft dafür
  `OSError`. Das bisherige gemeinsame `try/except` um Größe UND beide Zeitstempel hat dadurch auch
  die eigentlich intakte Dateigröße mit verworfen (~3435 betroffene Zeilen: 2034 auf `my_passport`,
  1401 auf `t7`, beide NTFS). Größe wird jetzt unabhängig von den Zeitstempeln behandelt, jeder
  Zeitstempel einzeln try/except (inkl. `OverflowError`/`ValueError` als Sicherheitsnetz für
  ähnliche Fälle).
- Bekannter, nicht gefixter Nebenpunkt: `afss scan`/`afss collect-metadata` können auf einer
  Windows-Konsole mit `UnicodeEncodeError` abstürzen, wenn die Zusammenfassung Sonderzeichen (`⚠`,
  kyrillische Dateinamen in Fehlermeldungen) enthält (cp1252-Codepage) - passiert erst beim
  abschließenden `print()`, alle DB-Schreibvorgänge sind zu dem Zeitpunkt bereits committet.
  Workaround: `PYTHONIOENCODING=utf-8` setzen oder `sys.stdout.reconfigure(encoding="utf-8")`.

**Datenstand:** `afss.db` + `config/artists.json`/`providers.json`/`studios.json` vom Windows-PC
(nach Scan + `collect-metadata` für alle vier Profile, inkl. obiger Reparatur) auf den Mac
zurückübertragen - identische Tagging-Zahlen wie vor dem PC-Durchgang (16486 `media_items`, 16390
mit Artist, 5847 mit Tags, 12277 manual_override, 1586 missing_since), zusätzlich 9135 neue
`media_technical_info`-Zeilen. Backup des vorherigen Mac-Standes unter `afss.db-pre-pc-merge-*.bak`.
