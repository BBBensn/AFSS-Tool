# AFSS-Tool

## Zweck

Konsolidiert Medien, die über mehrere externe Festplatten und ein NAS verteilt und unstrukturiert
gewachsen sind, in eine saubere, konsistent benannte und getaggte Jellyfin-Library. Kernprinzipien:
nichts wird destruktiv verändert bis explizit bestätigt, jeder Schritt ist idempotent (erneutes
Ausführen erzeugt keine Duplikate), alles läuft offline/lokal ohne externe Metadaten-APIs.

## Architektur

**SQLite (`afss.db`) ist die single source of truth.** Kern-Tabellen:
- `profiles` — ein Eintrag pro Platte/Root-Verzeichnis (`config/legacy_profiles.yml`)
- `media_items` — eine Zeile pro gefundener Datei, durchläuft den Status: gescannt →
  resolved (Artist/Provider zugeordnet) → geplant (`planned_filename`) → applied
  (`target_path`) → transcodiert (`transcoded_path`)
- `artists`/`providers` + `artist_aliases`/`provider_aliases` — Identitäten und ihre bekannten
  Namensvarianten (Ordnernamen), gefüttert aus `config/artists.json`/`providers.json`
- `unresolved_folders` — Ordnernamen, die keinem Artist/Provider zugeordnet werden konnten,
  Status: `pending` → `assigned_artist`/`assigned_provider`/`category`/`trash`/`ignored`
- `dedupe_groups`/`dedupe_group_members` — per Datei-Hash gefundene Duplikate

**Phasen-Module** (jeweils `afss/<name>.py`, CLI-Subcommand identisch benannt):
`scan` → `resolve` → `tag` (CLI oder `--web`) → `dedupe` → `plan` → `apply` → `transcode`.
Dazwischen einmalig `migrate-legacy-json` (Artists/Providers importieren) und bei Bedarf
`anonymize`/`migrate-mapping` für Text-Anonymisierung.

**Web-Oberflächen** (alle Flask, nur `127.0.0.1`):
- `afss/dashboard/` — zentrale Steuerung aller Phasen pro Profil, verlinkt Artist-Editor und
  Sortier-Studio
- `afss/artist_editor/` — Formular für `config/artists.json`, inkl. Bio-Text-Import
  (`afss/artist_editor/import_parsers.py`) von Babepedia/Boobpedia/Pornopedia; der Nutzer kopiert
  den Text selbst aus seinem Browser, das Tool ruft nichts live ab (offline-Prinzip bleibt gewahrt).
  Enthält außerdem eine Merge-Funktion (`afss/tagging.py::merge_entities`) für doppelt angelegte
  Artists: Name/Aliase des aufgelösten Eintrags werden Alias beim Ziel, zugeordnete `media_items`
  werden umgehängt, der Duplikat-Eintrag wird aus JSON und DB entfernt
- `afss/sort_web/` (Logik in `afss/sort_studio.py`) — Sortier-Studio: zeigt alle `media_items`
  eines Profils gruppiert nach Artist → Collection, Checkbox-Mehrfachauswahl (inkl. Gruppen-Auswahl
  und Shift-Klick-Bereichsauswahl) für Bulk-Neuzuordnung (Artist/Provider/Collection) und
  Titel-Override pro Datei. Setzt dabei `manual_override=1` auf betroffenen Zeilen, damit ein
  späterer `resolve`-Lauf die manuelle Entscheidung nicht überschreibt (siehe `afss/resolve.py`,
  überspringt Zeilen mit gesetztem Flag komplett). Zusätzlich: `item_status` (`trash`/`extra`, von
  `plan`/`apply` ausgeschlossen), freie `tags` pro Datei, `media_item_co_artists` für
  Coop/Feature-Videos (Hauptartist bestimmt weiterhin den Zielordner). Unterstützt außerdem
  `profile_id="all"` für eine profilübergreifende Ansicht (gleiche Konvention wie
  `dedupe_profile`/`apply_dedupe`) - wichtig für Artists, die über mehrere Platten verteilt sind

## Aktueller Datenstand (Momentaufnahme)

Drei Profile gescannt, ca. 14.600 Media-Items insgesamt (Stand 2026-09-11):

| Profil | Dateien | Resolved | Offene Tag-Ordner |
|---|---|---|---|
| elements | 3.551 | 2.552 (72 %) | 0 |
| untitled | 2.155 | 1.270 (59 %) | 0 |
| my_passport | 8.870 | 6.544 (74 %) | 0 |

`config/artists.json` enthält 221 Artists, `config/providers.json` 15 Provider (Stand nach dem
v1.2.0-Backfill, siehe Changelog — vorher waren 140 Artists/2 Provider nur in der DB, nicht im
JSON sichtbar).

## Bekannte offene Punkte

- **Compilation-Ordner** (ein Ordner mit Clips vieler, meist bereits bekannter Artists) — noch
  keine endgültige Entscheidung, ob einzeln in die jeweiligen Artist-Ordner aufgelöst oder als
  Platzhalter-Collection belassen; Empfehlung war: bei überschaubarem Aufwand auflösen, sonst
  vorerst unter einem `_Compilations`-Platzhalter sammeln und später gezielt nachziehen
- **Datenquellen wechselnd verfügbar** — externe Platten (`My Passport`, `Elements`, `Untitled`)
  sind nicht dauerhaft gemountet, NAS-Freigaben (`00_inbox` etc.) laufen über SMB und sind je nach
  Netzwerkstatus mal verbunden, mal nicht — vor jedem `scan`/`apply`/`transcode`-Lauf kurz prüfen

## Arbeitsweise

Das Tool ist für Selbstbedienung gebaut — `afss dashboard` und die CLI-Befehle laufen komplett
lokal, ohne dass eine Claude-Session mitlesen muss. Für den täglichen Sortier-/Tagging-Workflow
braucht es Claude nicht; Claude wird gezielt für neue Features, Fehleranalyse oder Rückfragen
hinzugezogen. Wenn dabei Beispieldaten geteilt werden müssen, bevorzugt anonymisiert
(`afss anonymize`) oder in reduzierter Form statt vollständiger Ordnerlisten mit Klarnamen.
