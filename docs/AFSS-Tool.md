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
- `studios` (+ `config/studios.json`) — Produzent, im Unterschied zu `providers` (Vertrieb). Anders
  als Artist/Provider (noch) keine automatische Ordnername-Auflösung, nur manuelle Zuordnung im
  Sortier-Studio (`media_items.studio_id`)
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
  werden umgehängt, der Duplikat-Eintrag wird aus JSON und DB entfernt. Sieben Freitext-Felder
  (Nationality, Ethnicity, Geburtsort, Bra Size, Artist Tags, Occupation, Piercings) haben
  Autocomplete aus bereits über andere Artists vergebenen Werten (`store.py::distinct_field_values`,
  Route `/artists/field-values`, feste Allow-Liste) - verhindert Nah-Duplikate durch Groß-/
  Kleinschreibung o.ä.; echte Festwert-Felder bleiben bei `<datalist>`. Die Artist-Liste hat einen
  Text-Filter und klickbar sortierbare Spalten (gleiches Muster wie im Sortier-Studio)
- `afss/tag_editor/` — Übersicht aller im Sortier-Studio vergebenen Tags mit Nutzungszähler
  (`sort_studio.py::list_all_tags`), Text-Filter, klickbar sortierbare Spalten. Umbenennen/
  Zusammenführen/Entfernen direkt in der Liste (Autocomplete, nutzt `rename_tag()` weiter) - kein
  eigener `config_dir` nötig, da Tags reiner DB-Freitext ohne JSON-Store sind. Route `/tags/` (auch
  im Dashboard registriert), eigenständiger Befehl `afss tags`
- `afss/sort_web/` (Logik in `afss/sort_studio.py`) — Sortier-Studio: zeigt alle `media_items`
  eines Profils gruppiert nach Artist → Collection, Checkbox-Mehrfachauswahl (inkl. Gruppen-Auswahl,
  Shift-Klick-Bereichsauswahl und "Alle Treffer auswählen" - markiert alle aktuell sichtbaren,
  gefilterten Dateien gruppenübergreifend) für Bulk-Neuzuordnung (Artist/Provider/Collection) und
  Titel-Override pro Datei. Setzt dabei `manual_override=1` auf betroffenen Zeilen, damit ein
  späterer `resolve`-Lauf die manuelle Entscheidung nicht überschreibt (siehe `afss/resolve.py`,
  überspringt Zeilen mit gesetztem Flag komplett). Zusätzlich: `item_status` (`trash`/`extra`, von
  `plan`/`apply` ausgeschlossen), freie `tags` pro Datei, `media_item_co_artists` für
  Coop/Feature-Videos (Hauptartist bestimmt weiterhin den Zielordner). Unterstützt außerdem
  `profile_id="all"` für eine profilübergreifende Ansicht (gleiche Konvention wie
  `dedupe_profile`/`apply_dedupe`) - wichtig für Artists, die über mehrere Platten verteilt sind.
  Artist/Provider lassen sich explizit entfernen (nicht nur der Auto-Resolve-Override aufheben),
  und `dissolve_collection()` löst einen Collection-Ordner auf (Dateien verlieren die
  Collection-Zuordnung, der Ordnername wird stattdessen als Tag übernommen). Artists lassen sich
  sperren (`sort_studio_locks`, global über alle Profile) - bleiben dauerhaft zugeklappt und von
  Bulk-Aktionen ausgenommen, als Fortschrittsmarker. Aktionen laufen als AJAX-Swap (Server rendert
  die Seite direkt in derselben Response, Frontend tauscht nur `#app-root` per `fetch()` aus) statt
  über einen klassischen Redirect+Reload - dadurch bleiben Scroll-Position und Gruppenzustand beim
  Speichern ohne Sprung erhalten. Fehler in einer Aktion werden serverseitig abgefangen und als
  Flash-Hinweis mit der echten Ursache angezeigt statt als nichtssagender 500er (gleiches Muster wie
  `dashboard/app.py::run_action`), zusätzlich fängt ein blueprint-weiter Error-Handler auch Fehler
  beim Rendern selbst ab. `MAX_FORM_MEMORY_SIZE` ist bewusst deaktiviert (`create_app()` in
  `dashboard/app.py` und `sort_web/app.py`), da Flasks 500-KB-Standardlimit bei großen Auswahlen in
  der `all`-Ansicht (viele tausend `item_id`-Checkboxen) sonst mit `413 Request Entity Too Large`
  jede Aktion blockiert - für dieses rein lokale Single-User-Tool unkritisch. Ebenso deaktiviert:
  `MAX_FORM_PARTS`, das nur für `multipart/form-data` gilt (genau das, was das Sortier-Studio-JS per
  `fetch()`+`FormData` sendet) und beim Überschreiten *stillschweigend* auf ein leeres Formular
  zurückfällt statt einen Fehler zu werfen - eine Auswahl über 1000 Dateien führte dadurch zu einem
  Klick, der sichtbar nichts tat. Ein `isBusy`-Flag im Frontend verhindert außerdem parallele
  Doppel-Anfragen bei ungeduldigen Mehrfachklicks, mit sichtbarem "Wird gespeichert..."-Hinweis; der
  Dev-Server läuft mit `threaded=True`, damit eine große Anfrage nicht den einzigen Worker blockiert.
  Die Dateitabelle zeigt pro Zeile zusätzlich den zugeordneten Artist-Namen als eigene Spalte. Die
  Tabellen-Kopfzeile lässt sich per Toggle fixieren (bleibt beim Scrollen unter der Toolbar stehen,
  Offset wird per JS an die aktuelle Toolbar-Höhe angepasst), Titel-Override/Tags-Felder zeigen den
  vollen Wert als Hover-Tooltip. `search_tags()` liefert Autocomplete-Vorschläge für Tags (dedupliziert
  aus der kommaseparierten `media_items.tags`-Spalte, da Tags anders als Artists/Providers keine
  eigene Tabelle haben) - genutzt sowohl im Toolbox-Tags-Feld als auch pro Zeile. Tabellen-Spalten
  (Artist, Studio, Collection, Provider, Status, Co-Artists, Titel-Override, Tags) sind einzeln
  ein-/ausblendbar (Menü neben dem Kopfzeilen-Pin, `localStorage`) - damit das Layout auch mit
  künftigen weiteren Kategorien nicht zu voll wird; Studio startet standardmäßig ausgeblendet.
  Klick auf eine Spaltenüberschrift sortiert client-seitig (Werte stehen als `data-sort-*`-
  Attribute im DOM) *innerhalb* jeder bestehenden Artist-/Collection-Gruppe, erneuter Klick kehrt
  die Richtung um - unabhängig vom server-seitigen "Sortieren"-Dropdown, das stattdessen die
  Gruppierung selbst bestimmt (Collection-Unterordner vs. flache Liste).
  `rename_tag()` benennt einen Tag exakt (case-sensitive) profilübergreifend über ALLE Dateien um
  oder entfernt ihn (leeres Ziel) - zum Bereinigen versehentlicher Nah-Duplikate, ohne jede
  betroffene Datei einzeln durchklicken zu müssen; im UI über ein Panel in "Verwaltung" erreichbar.
  `save_title_overrides()`/`save_tags()` geben `(geprüft, geändert)` zurück statt nur der
  Gesamtzahl - das Formular schickt immer den Wert jeder sichtbaren Zeile mit (nicht nur
  bearbeitete), ohne die separate "geändert"-Zahl wäre bei vielen hundert Dateien nicht erkennbar,
  ob versehentlich eine falsche Zeile mitgeändert wurde

## Aktueller Datenstand (Momentaufnahme)

Vier Profile gescannt, ca. 16.000 Media-Items insgesamt (Stand 2026-09-11):

| Profil | Dateien | Resolved | Offene Tag-Ordner |
|---|---|---|---|
| elements | 3.551 | 2.552 (72 %) | 0 |
| untitled | 2.155 | 1.270 (59 %) | 0 |
| my_passport | 8.870 | 6.544 (74 %) | 0 |
| t7 | 1.445 | 155 (10,7 %) | frisch gescannt, noch zu taggen |

`config/artists.json` enthält 183 Artists (nach Merges/Bereinigung, siehe v1.3.0/v1.4.1-Changelogs),
`config/providers.json` 15 Provider.

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
