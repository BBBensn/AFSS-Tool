# AFSS-Tool — Projekt-CLAUDE.md
Projekt-spezifische Ergänzung zur globalen `~/.claude/CLAUDE.md`. Ergänzt, überschreibt nie.

---

## Projekt-Basics

- Name: `afss`
- Version: `1.27.1`
- Beschreibung: Konsolidiert unstrukturierte Medien-Bibliotheken (verteilt über mehrere externe
  Festplatten/NAS) in eine saubere, benannte, getaggte Jellyfin-Library. SQLite (`afss.db`) als
  single source of truth statt verstreuter Skripte mit eigenem State.
- Stack: Python 3.10+, Flask, SQLite, PyYAML, pytest
- Externe Systemabhängigkeit (kein pip-Paket): `ffmpeg`/`ffprobe` — muss auf der ausführenden
  Maschine separat vorhanden sein (Mac: via Homebrew, bereits installiert; Windows: z. B.
  `winget install ffmpeg`)
- Läuft komplett offline/lokal — kein Netzwerkzugriff, keine externen APIs für Metadaten
  (bewusste Entscheidung, siehe ursprüngliches Projekt-Briefing)

## Server & Deploy

Kein Server-Deploy — lokales CLI-Tool, läuft auf der Maschine des Nutzers (aktuell Mac, geplant
auch Windows-PC mit Nvidia-GPU für `afss transcode`). Die generische Hetzner-Deploy-Sektion aus der
globalen CLAUDE.md trifft auf dieses Projekt nicht zu.

## Git

- Remote: `git@github.com:BBBensn/AFSS-Tool.git` (SSH, bereits korrekt eingerichtet)
- Standard-Branch: `main` (entspricht globalem Default)

## Versionierung

- Aktuell: `v1.27.1`
- Kurze Historie:
  - `v1.0.0` — Grundgerüst: Datenmodell, `scan`/`resolve`/`tag`/`anonymize`/`dedupe`/`plan`/`apply`,
    Web-Dashboard, Artist-Metadaten-Editor inkl. Bio-Import
  - `v1.1.0` — `afss transcode` (Video-Normalisierung auf MP4/HEVC)
  - `v1.2.0` — Bugfixes: SQLite WAL-Modus + Busy-Timeout gegen "database is locked", Sync-Lücke
    zwischen Tag-UI und `artists.json`/`providers.json` geschlossen (write-through + Backfill,
    140 Artists + 2 Provider ergänzt), neuer Befehl `afss sync-identities`
  - `v1.3.0` — Artist-Merge im Artist-Editor: doppelt angelegte Artists mit dem richtigen Eintrag
    zusammenführen statt nur zu löschen (Alias- und Dateizuordnung wird übernommen)
  - `v1.4.0` — Sortier-Studio: neue Dashboard-Ansicht pro Profil für manuelle Bulk-Umsortierung
    (Artist/Provider/Collection/Titel), manuelle Zuordnungen überstehen künftige `resolve`-Läufe
  - `v1.4.1` — Bugfix: Artist-Editor synct jetzt auch in die DB (nicht nur JSON), Sortier-Studio-
    Suche fragt JSON statt DB ab; Bedienkomfort (Alle zu-/aufklappen, Gruppen-Auswahl, Shift-Klick)
  - `v1.5.0` — Sortier-Studio: Dateistatus (trash/extra, von plan/apply ausgeschlossen), Tags pro
    Datei, Co-Artists für Coop/Feature-Videos (Hauptartist bestimmt weiterhin den Zielordner)
  - `v1.6.0` — Sortier-Studio: profilübergreifende Ansicht (`profile_id="all"`) für Artists, die
    über mehrere Platten verteilt sind, inkl. Herkunfts-Badge und Platten-Filter
  - `v1.7.0` — Sortier-Studio: Artist/Provider explizit entfernen, Collections auflösen (Ordner
    → Tag); viertes Profil "T7" eingerichtet (bereits sortiert, Daten unter T7/other/)
  - `v1.7.1` — Bugfix: Performance-Hänger bei großen Profilen (Gruppen ab 150 Dateien eingeklappt,
    Filter debounced); Sortier-Studio-Zeilen in klare Spalten mit Kopfzeile umgebaut
  - `v1.8.0` — Sortier-Studio: neue Artists/Provider direkt anlegen, wenn die Suche keinen Treffer
    liefert ("Neu anlegen & setzen"), statt erst über den Artist-Editor gehen zu müssen
  - `v1.9.0` — Sortier-Studio: Filter-Bug behoben (Kopfzeile brach die Filterung ab), Treffer
    klappen Gruppen automatisch auf, neue Sortierung nach Dateiname/Dateityp/Ursprungsordner
    (löst Collection-Gruppierung dabei auf, Collection bleibt als Spalte sichtbar)
  - `v1.10.0` — Sortier-Studio: "Alles setzen"-Button (mehrere Felder in einem Klick), Layout
    (aufgeklappte Gruppen, Filter, Scroll-Position, Sortierung) übersteht jetzt einen Save
  - `v1.11.0` — Sortier-Studio: keine echte Seitennavigation mehr bei Aktionen (AJAX-Swap statt
    Redirect+Reload), neuer Artist-Lock (🔒/🔓, wie gesperrter Layer in Photoshop) als
    Fortschrittsmarker - bleibt zugeklappt, von Bulk-Aktionen ausgenommen, global gespeichert
  - `v1.12.0` — Bugfix: `/sort/*`-Routen fingen Fehler nicht ab und zeigten nur ein nichtssagendes
    "Aktion fehlgeschlagen" statt der echten Ursache; Toolbox neu gruppiert (Ansicht/Artist/
    Provider/Collection/Status/Co-Artist/Tags/Verwaltung) mit Icon-Buttons statt Textbuttons
    (Tooltip on hover), "Alles setzen" jetzt unten rechts als letztes Element
  - `v1.13.0` — blueprint-weiter Error-Handler als zusätzliches Sicherheitsnetz gegen verbleibende
    500er in `/sort/*`; Toolbox nach Design-Vorlage überarbeitet (zweizeiliges Layout, einheitliche
    Strich-Icons, größere Abstände)
  - `v1.14.0` — Root Cause für "Aktion fehlgeschlagen" gefunden: Flasks 500-KB-Formular-Limit
    (`MAX_FORM_MEMORY_SIZE`) griff bei großen Auswahlen in der `all`-Ansicht - jetzt deaktiviert;
    neue "Artist"-Spalte in der Dateitabelle; Toolbox-Reihenfolge neu (Ansicht nur Filter, Sortieren
    als eigene Box zwischen Tags und Verwaltung)
  - `v1.15.0` — zweite Formular-Limit-Ursache gefunden (`MAX_FORM_PARTS`, betrifft multipart/
    form-data - genau das, was das Sortier-Studio-JS per `fetch()`+`FormData` sendet, faellt beim
    Ueberschreiten *stillschweigend* auf ein leeres Formular zurueck statt einen Fehler zu werfen);
    Doppel-Klick-Schutz + "Wird gespeichert..."-Hinweis; Dev-Server laeuft jetzt `threaded=True`
  - `v1.16.0` — Tabellen-Kopfzeile per Toggle fixierbar (bleibt beim Scrollen stehen); Titel-
    Override/Tags-Felder zeigen den vollen Text als Hover-Tooltip; neue Autocomplete fuer Tags
    (Toolbox + pro Zeile), dedupliziert aus bereits vergebenen Werten
  - `v1.17.0` — neue Kategorie "Studio" (Produzent, eigene Toolbox-Box + Spalte, wie Artist/
    Provider); Tabellen-Spalten jetzt ein-/ausblendbar (Menü im Kopfzeilen-Bereich, gemerkt per
    localStorage) - loest das absehbare Problem, dass immer mehr Kategorien das Layout sprengen
  - `v1.18.0` — Tag global umbenennen/entfernen (⇄-Button in Verwaltung, Panel mit Autocomplete,
    wirkt profilübergreifend auf alle Dateien mit exaktem Tag); "Titel & Tags speichern" zeigt jetzt
    zusaetzlich, wie viele der (immer alle sichtbaren) Felder tatsaechlich geaendert wurden
  - `v1.18.1` — Bugfix: "Tag ersetzen"-Panel liess sich nicht auf-/zuklappen (CSS `display: flex`
    ueberschrieb das `hidden`-Attribut); mehrere Co-Artists pro Datei sauberer dargestellt (Flex-
    Umbruch + Hover-Tooltip mit allen Namen)
  - `v1.19.0` — neuer Button "Alle Treffer auswaehlen" unter dem Filterfeld: markiert alle aktuell
    sichtbaren (gefilterten) Dateien gruppenuebergreifend auf einen Schlag, statt jede
    Artist-/Collection-Gruppe mit Treffern einzeln anhaken zu muessen
  - `v1.20.0` — Tabellen-Kopfzeile klickbar: sortiert wie in Tabellenprogrammen ueblich innerhalb
    jeder Artist-/Collection-Gruppe (kollidiert nicht mit dem bestehenden Sortieren-Dropdown),
    erneuter Klick kehrt die Richtung um, uebersteht wie Filter/Scroll-Position einen Save
  - `v1.21.0` — Artist-Editor Schritt 1/4: Autocomplete fuer sieben Freitext-Felder (Nationality,
    Ethnicity, Geburtsort, Bra Size, Artist Tags, Occupation, Piercings), Artist-Liste mit
    Text-Filter, drei neuen Spalten und klickbarer Sortierung
  - `v1.22.0` — Schritt 2/4: neuer Tag-Editor (`afss/tag_editor/`, Route `/tags/`, Befehl
    `afss tags`) - Uebersicht aller vergebenen Tags mit Nutzungszaehler, Umbenennen/Zusammenfuehren/
    Entfernen direkt in der Liste mit Autocomplete, nutzt `rename_tag()` aus dem Sortier-Studio weiter
  - `v1.23.0` — Schritt 3/4: einheitliche Nav-Leiste (Dashboard/Sortier-Studio/Artists/Tags) auf
    allen fuenf Seiten statt uneinheitlicher Rueck-Links; feste relative Pfade statt url_for, damit
    es sowohl im Dashboard als auch standalone funktioniert
  - `v1.24.0` — Schritt 4/4 (Abschluss): visueller Politur-Pass - verfeinerte Sortier-Studio-
    Farbpalette auf Dashboard/Artist-Liste/Artist-Formular/Tag-Editor uebertragen, primaere Aktionen
    in Akzentfarbe; dabei zwei CSS-Spezifitaets-Kollisionen gefunden und behoben
  - `v1.25.0` — Gender/Sex/Orientation ueberarbeitet: `sex_assigned_at_birth` um `intersex` ergaenzt;
    `gender_identity`s `trans`-Wert entfernt (Datenpruefung zeigte: trans wird bereits verlustfrei
    ueber Kombination beider Felder ausgedrueckt, ein eigener Wert haette Frau/Mann-Info verschluckt);
    neues Feld `sexual_orientation`, bei allen 225 Artists mit `pansexual` vorbelegt
  - `v1.26.0` — vier versehentlich in der echten `config/artists.json`/DB gelandete Test-Dummies
    entfernt; Artist-Liste: Bulk-Bearbeitung (Artists markieren, ein `default_tags`-Feld mit
    Autocomplete bei allen gesetzt) sowie Spalten ein-/ausblenden sowie Kopfzeile fixieren, wie im
    Sortier-Studio (aber bewusst ohne dessen AJAX-Swap - bei ~220 Artists reicht Redirect)
  - `v1.27.0` — Artist-Liste: Kopfzeile-Fixieren repariert (Root Cause war `overflow: hidden` auf
    der Tabelle, brach `position: sticky` in jedem Browser, nicht nur Safari); alle 24 sinnvollen
    `default_tags`-Felder jetzt als Spalte verfuegbar statt nur 6; "Auswahl wiederholen"-Button nach
    Bulk-Aktionen (Artist-Liste + neues Icon im Sortier-Studio), damit dieselbe Gruppe nacheinander
    mehrfach bearbeitet werden kann; Header-Buttons (Lock/Spalten) jetzt tatsaechlich rechtsbuendig
  - `v1.27.1` — Bugfix: Spalten-Vorbelegung nach v1.27.0 kaputt (alter localStorage-Wert `[]` aus der
    6-Spalten-Zeit liess alle 24 Spalten aufgeklappt starten) - neuer localStorage-Key, startet wieder
    sauber mit nur den bisherigen sechs Standard-Spalten sichtbar

## Changelogs & Dokumentation

- Changelog-Pfad: `docs/changelogs/`
- Projekt-Dokumentation: `docs/AFSS-Tool.md` (lokal im Repo, **nicht** im Obsidian-Vault —
  abweichend vom globalen Standard-Pfad, da der Nutzer das für dieses Projekt explizit so
  entschieden hat, um das iCloud-Sync-Risiko zu vermeiden; er kopiert bei Bedarf selbst in den
  Vault)

## Roadmap

- ✅ Datenmodell + `scan`/`resolve`/`migrate-legacy-json`/`report`
- ✅ `tag` (CLI + Web-UI), `anonymize` (konsolidiert `json_cleaner`/`omni_cleaner`), `dedupe`,
  `plan`, `apply`
- ✅ Web-Dashboard (`afss dashboard`) — zentrale Oberfläche für alle Phasen
- ✅ Artist-Metadaten-Editor (`afss artists`, auch im Dashboard verlinkt) inkl. Bio-Import von
  Babepedia/Boobpedia/Pornopedia (Paste-Text, kein Live-Fetch), Partial-Dates (Jahr/Monat/Tag
  einzeln), Lowercase- und ISO-3166-Normalisierung
- ✅ Video-Transcoding (`afss transcode`, v1.1.0) — Encoder-Erkennung zur Laufzeit
  (VideoToolbox/NVENC/QSV/libx265), läuft unverändert auf Mac oder Windows-PC
- ✅ Profil `my_passport` fertig taggen (Stand 2026-09-11: scan, resolve, alle Ordner getaggt,
  74 % resolved)
- ✅ Artist-Merge im Artist-Editor (v1.3.0) — doppelt angelegte Einträge sauber zusammenführen
- ✅ Sortier-Studio (v1.4.0) — manuelle Bulk-Umsortierung (Artist/Provider/Collection/Titel) pro
  Profil im Dashboard, übersteht künftige `resolve`-Läufe
- ✅ Vierte Platte "T7" als Profil eingerichtet, gescannt und resolved (2026-09-11)
- ⬜ Erster kompletter Realdaten-Durchlauf (scan→resolve→tag→dedupe→plan→apply→transcode) für
  mindestens ein Profil bis zum Ende
- ⬜ (Zukunftsvision, noch kein Auftrag) Dropfolder-Automatisierung: neue Dateien landen in einem
  Ordner, werden automatisch transcodiert/benannt/einsortiert, bevor sie ans NAS gehen

## Stack-Notizen

- `ffmpeg`-Encoder-Wahl ist plattformabhängig automatisch (siehe `afss/transcode.py`) — beim
  Wechsel auf eine neue Maschine nichts anzupassen, nur `ffmpeg` dort installieren
- Reales `config/artists.json`/`providers.json`/`legacy_profiles.yml`/`mapping.json` sind bewusst
  `.gitignore`d (enthalten unanonymisierte Personendaten bzw. verraten Laufwerksnamen/Kategorien) —
  nur Beispiel-/Cleaned-Varianten sind versioniert
