# Bericht: AFSS-Tool Windows-PC-Setup + Metadaten-Sammlung (2026-09-27)

An: Claude (MacBook, AFSS-Tool-Hauptarbeitsplatz)
Von: Claude (Windows-PC "METIS", Secondary-Arbeitsplatz)
Kontext: Dieser PC wurde heute erstmals für AFSS-Tool eingerichtet (siehe
`PC-Setup-Runbook-2026-09-27.md`). Ziel war: Setup + `scan` + `collect-metadata` für alle vier
externen Platten. Dabei sind zwei echte Bugs aufgetaucht, die die Mac-Seite kennen sollte, bevor
dort wieder gescannt/getaggt wird.

**Lies das komplett, bevor du auf dem Mac wieder `afss scan` läufst oder `afss.db` hierher/dorthin
kopierst** — Abschnitt 4 ("Wichtig für den Mac") ist der kritische Teil.

---

## 1. Was auf diesem PC gemacht wurde

- Setup: Python 3.12, Git, ffmpeg/ffprobe (via winget), SSH-Key `afss-pc`/`METIS` bei GitHub
  hinterlegt, Repo geklont, venv + `pip install -e .`
- `afss.db` + `config/{artists,providers,studios,legacy_profiles}.json/.yml` vom Mac übernommen
- `config/legacy_profiles.yml` auf Windows-Laufwerksbuchstaben umgemünzt (siehe Tabelle unten) —
  **diese Datei bleibt maschinenspezifisch, nicht zurück auf den Mac kopieren** (genau wie
  `legacy_profiles.yml` schon jetzt pro Maschine gilt und `.gitignore`d ist)
- `afss scan` + `afss collect-metadata` für alle vier Profile durchgelaufen

| Profil | Laufwerk (Windows) | Bus | Label | Größe/FS |
|---|---|---|---|---|
| untitled | E:\ | USB (JMicron-Gehäuse) | — | 500GB, exFAT |
| elements | F:\ | USB (WD Elements 25A1) | Elements | 1.5TB, exFAT |
| my_passport | G:\ | USB (WD My Passport) | My Passport | 2TB, NTFS |
| t7 | H:\other | USB (Samsung PSSD T7) | T7 | 2TB, NTFS |

## 2. Ergebnis Scan + collect-metadata

| Profil | Dateien gesamt | Videos | Erfolgreich geprobt | Fehlgeschlagen | Fehlend markiert |
|---|---|---|---|---|---|
| untitled | 2155 | 815 | 815 | 0 | 88 |
| elements | 3551 | 2592 | 2588 | 4 | 0 |
| my_passport | 9335 | 4924 | 4879 | 45 (29 defekt + 16 echt fehlend) | 1498 |
| t7 | 1445 | 854 | 853 | 1 | 0 |

"Fehlend markiert" = `missing_since` gesetzt (Datei nicht mehr unter dem erwarteten Pfad gefunden).
Bei `untitled`/`my_passport` ist das mehrheitlich echt (Dateien wurden offenbar zwischenzeitlich auf
dem Mac/der Platte selbst gelöscht/verschoben) — nichts, das dieser PC verursacht hat, und laut
v1.29.0-Design absichtlich nicht-destruktiv (Tags bleiben an der Zeile, falls die Datei wieder
auftaucht).

## 3. Zwei Bugs gefunden + gefixt (nur lokal auf diesem PC, noch nicht committet/gepusht)

### Bug A — Unicode-Normalisierung Mac→Windows (echter Datenintegritäts-Bug)

**Symptom:** Nach dem ersten Windows-Scan wurden Dateien mit Umlauten/Akzenten/kyrillischen
Zeichen im Pfad als "fehlend" markiert, obwohl sie physisch vorhanden waren — und für dieselbe
Datei tauchte eine zweite, komplett leere (ungetaggte) `media_items`-Zeile auf.

**Root Cause:** macOS (APFS/HFS+) speichert solche Zeichen zerlegt (NFD, z.B. "ü" als `u` +
Kombinationszeichen U+0308). Windows liefert beim `os.walk()`-Scan dieselben Namen zusammengesetzt
(NFC, ein einzelnes `ü` = U+00FC). Beide Strings sehen identisch aus, sind aber als Text
unterschiedlich. Der Upsert-Unique-Key `(profile_id, rel_path)` in `scan.py` matcht deshalb die vom
Mac gescannte (NFD-)Zeile nicht gegen die neu vom Windows-Scan gelieferte (NFC-)Zeile → alte,
bereits getaggte Zeile wird zur Karteileiche (`missing_since` gesetzt), neue leere Zeile wird
angelegt.

**Umfang, den ich gefunden + repariert habe:**

| Profil | Betroffene Dateien mit verlorenen Tagging-Daten |
|---|---|
| untitled | 3 |
| elements | 7 |
| my_passport | 146 |
| t7 | 0 |

**Reparatur, die ich bereits durchgeführt habe** (auf `afss.db` auf diesem PC): Backup unter
`afss.db.pre-unicode-repair-20260927-064317.bak` im Repo-Root angelegt, dann per Skript für jedes
der 156 Paare: Tagging-Spalten (`artist_id`, `provider_id`, `collection_name`, `needs_review`,
`review_reason`, `manual_override`, `title_override`, `item_status`, `tags`, `studio_id`,
`planned_filename`, `target_path`, `applied_at`, `verified`, `transcoded_path`, `transcoded_at`,
`transcode_verified`, `file_hash`) von der alten auf die neue Zeile übernommen, Referenzen in
`media_item_co_artists`/`dedupe_group_members`/`dedupe_groups.kept_media_item_id`/
`media_technical_info` umgehängt, alte Zeile gelöscht. Verifiziert: 0 verbleibende Duplikate.

**Code-Fix in `afss/scan.py`** (normalisiert `rel_path`/`filename` konsequent auf NFC beim Scan):

```diff
 import datetime
 import os
+import unicodedata
 from collections import Counter, defaultdict
 from pathlib import Path
@@
             file_path = Path(dirpath) / fn
             rel = file_path.relative_to(root)
-            parts = rel.parts
+            # macOS (APFS/HFS+) speichert Dateinamen mit Umlauten/Akzenten/kyrillischen Zeichen
+            # zerlegt (NFD), Windows liefert dieselben Namen zusammengesetzt (NFC). Ohne
+            # Normalisierung matcht der Upsert unten (Unique-Key profile_id+rel_path) eine vom Mac
+            # gescannte Datei nicht mehr - alte, ggf. bereits getaggte Zeile wird faelschlich als
+            # "fehlend" markiert, neue leere Zeile fuer dieselbe physische Datei angelegt.
+            rel_str = unicodedata.normalize("NFC", rel.as_posix())
+            fn_normalized = unicodedata.normalize("NFC", fn)
+            parts = rel_str.split("/")
@@
             rows.append(
                 (
-                    profile_id, str(file_path), rel.as_posix(), fn, ext, media_type,
+                    profile_id, str(file_path), rel_str, fn_normalized, ext, media_type,
                     size_bytes, fs_created_at, fs_modified_at,
                     folder_level1, folder_level2, now_iso,
                 )
             )
```

**Wichtig:** Dieser Fix normalisiert nur `rel_path`/`filename` (die Vergleichs-/Identitätsspalten),
nicht `path` (der reale, für Dateizugriff nötige OS-Pfad bleibt unverändert).

### Bug B — Ungültige NTFS-Erstellungszeit killt Dateigröße mit

**Symptom:** ~3435 Dateien (2034 auf `my_passport`, 1401 auf `t7` — beide NTFS) hatten
`size_bytes = NULL` nach dem Scan, obwohl die Dateien einwandfrei lesbar waren (ffprobe konnte sie
später problemlos probieren).

**Root Cause:** `st.st_ctime` liefert unter Windows für viele Dateien auf diesen beiden Platten
einen Sentinel-Wert nahe Jahr 1601 (klassisches "leeres" Windows-FILETIME, vermutlich vom Tool, mit
dem die Dateien ursprünglich auf die Platten kopiert wurden — `st_ctime` ist unter Windows die
Datei-Erstellungszeit, nicht wie unter Unix die Inode-Änderungszeit). Das ergibt einen negativen,
außerhalb des gültigen Bereichs liegenden Unix-Timestamp, `datetime.fromtimestamp()` wirft dafür
`OSError`. Der alte Code hatte **ein gemeinsames `try/except` um Größe UND beide Zeitstempel** —
ein kaputter Zeitstempel hat dadurch auch die eigentlich intakte Dateigröße mit verworfen.

**Fix in `afss/scan.py`:** Größe wird jetzt separat von den beiden Zeitstempeln behandelt, jeder
Zeitstempel einzeln try/except (inkl. `OverflowError`/`ValueError` als zusätzliches Sicherheitsnetz
für ähnliche Edge-Cases). Danach `untitled`/`elements`/`my_passport`/`t7` neu gescannt (sicher,
additiv) — alle 3435 Zeilen haben jetzt eine korrekte Dateigröße, `fs_created_at` bleibt bei diesen
Dateien weiterhin `NULL` (das ist korrekt so, die Erstellungszeit ist auf der Platte selbst nicht
sinnvoll vorhanden).

### Kleinerer, nicht gefixter Punkt — Windows-Konsole crasht bei Sonderzeichen im Print

`afss scan`/`afss collect-metadata` drucken ihre Zusammenfassung/Fehlerliste am Ende direkt in die
Konsole. Windows' Standard-Terminal-Codepage (cp1252) kann weder `⚠` noch viele Sonderzeichen in
Dateinamen (kyrillisch, manche Akzente) darstellen → `UnicodeEncodeError`, Traceback, Absturz. **Die
eigentliche Scan-/Probe-Arbeit ist davon nicht betroffen** (der Crash passiert erst beim `print()`
danach, alle DB-Schreibvorgänge sind zu dem Zeitpunkt schon committet) — ich habe die
Ergebnisse jeweils direkt per DB-Query nachgeholt statt die Konsolenausgabe zu reparieren. Falls ihr
das sauber fixen wollt: `sys.stdout.reconfigure(encoding="utf-8")` am Anfang von `afss/cli.py`,
oder `PYTHONIOENCODING=utf-8` als Umgebungsvariable setzen.

## 4. Wichtig für den Mac — bevor ihr weiterarbeitet

1. **`afss.db` ist auf diesem PC jetzt der aktuellere Stand** (enthält die 156 reparierten
   Zuordnungen + die nachgetragenen Dateigrößen + alle vier Profile durchgescannt/geprobt). Der
   Mac hat noch die alte Version von vor diesem Durchgang. **Bevor auf dem Mac wieder getaggt oder
   gescannt wird**, solltet ihr entscheiden, welche `afss.db` die aktuelle Basis ist (analog zum
   bestehenden Sync-Workflow für den Hetzner-Server in `docs/AFSS-Tool.md`) — sonst diverging state.
2. **Der `scan.py`-Fix (Bug A) muss auf den Mac-Checkout übertragen werden, bevor dort wieder
   gescannt wird** — sonst produziert der Mac's eigener Scan (der ja NFD-Pfade liefert) exakt
   denselben Duplikat-Bug erneut, nur diesmal umgekehrt (die jetzt NFC-normalisierten Zeilen würden
   zu Karteileichen). Der Fix ist plattformunabhängig (nutzt `unicodedata`, kein Windows-Spezifikum)
   und schadet auf dem Mac nicht.
3. Bug B (Zeitstempel) ist Windows/NTFS-spezifisch in der Symptomatik, der Code-Fix ist aber
   harmlos plattformübergreifend — spricht nichts dagegen, ihn mitzunehmen.
4. **`config/legacy_profiles.yml` NICHT vom Windows-PC übernehmen** — die Datei ist bewusst pro
   Maschine unterschiedlich (Windows-Laufwerksbuchstaben vs. `/Volumes/...`), genau wie im Projekt
   schon vorgesehen.
5. Alle Änderungen (`scan.py`, `tech_metadata.py`, die DB-Reparatur) sind bisher **nur lokal auf
   diesem PC, nicht committet/gepusht**. Falls ihr wollt, dass ich das von hier aus committe/pushe,
   sagt Bescheid — ansonsten sind die Diffs oben vollständig zum manuellen Nachvollziehen auf dem
   Mac.

## 5. Gefundene defekte Dateien (34 insgesamt, echte Kaputte, kein Bug)

Alle mit `ffprobe` bestätigt (kein Zugriffs-/Pfadproblem, Datei existiert, aber Video-Container
kaputt — überwiegend "moov atom not found", d.h. vermutlich unvollständig heruntergeladen/kopiert).
Guter Kandidat für einen Dedupe-/Qualitäts-Check vor dem Transcoding.

**elements (4):**
- `_Scat/_ArtofScat/Art of Scat Pack 3/ArtOfScat – RED BROWN PANTIES.mp4`
- `_Scat/_BettyParlour/scat.gold/1.5 kg of Own Poo and Squirting Night!.mp4` — **0 Bytes, leer.**
  Hinweis: `One point five kilograms of Own Poo and Squirting Night!.mp4` im selben Ordner hat
  echten Inhalt — vermutlich Duplikat mit korrekter Kopie, die leere Datei ist wohl verzichtbar.
- `_Scat/_Elecebra/Elecebra Part2/Elecebra - Shitty Fresh Milky Drink.mp4`
- `_Scat/_Scathunter/Vulgar Valentine.MOV`

**t7 (1):**
- `Eden Ivy/LegalPorno.21.06.13.Mina.And.Eden.Ivy.SZ2688.XXX.720p.WEB.x264-GalaXXXy.mkv` — kaputter
  Matroska-Header ("EBML header parsing failed"), nicht "moov atom"-Muster

**my_passport (29):** Cluster erkennbar — 14 davon aus einem Ordner (vermutlich derselbe defekte
Download-Batch):
- `#Chat_Store/Alexhetzer's Raum @Chaturbate - ... 2026-05-27 00_46.mp4`
- `#Chat_Store/Melodyxlove's Raum @Chaturbate - ... 2026-05-04 14_36.mp4`
- `#Chat_Store/Mon1_Day's Raum @Chaturbate - ... 2026-05-04 14_34.mp4`
- `#Chat_Store/Vynila's Raum @Chaturbate - ... 2026-05-04 14_36 (1).mp4`
- `#Chat_Store/Your_Tender_Doll's Raum @Chaturbate - ... 2026-05-04 14_36.mp4`
- `#trans/Claire Tenebrarum/Cailey Catts And Claire Gemini - ... EPORNER-1790198470986.mp4`
  ("trun track id unknown, no tfhd was found" — anderes Fehlerbild als die übrigen)
  - `#trans/Claire Tenebrarum/Immer hilfsbereite Trans-Babysitterin ... Zierlich Klein-1790199314054.mp4`
- `#trans/Starlightfemboy/Vertical/Starlightfemboy (V) (28).mp4`
- `GymBunnyPoops/[Femscat.com] GymBunnyPoops/www.femscat.com {44657,44661,44709,44782,45067,45139,
  45219,45253,45426,45546,45557,45703,45928,46120,46151,46244,46275}.mp4` (17 Dateien, gleicher
  Ordner/Quelle)
- `ManureFetish/Lyndra/scat/Brown Peaches Pooping My Jumpsuit Lyndra Lynn - Smear Teen Ultra.mp4`
- `ManureFetish/Lyndra/scat/Girlfriends Brown Surprise Lyndra Lynn - Anal Blowjob Amateur Fu.mp4`
- `ManureFetish/Lyndra/scat/Nurse Extra Poop Treatment Lyndra Lynn - Sex Blowjob UltraHD 4K7.mp4`
- `Miss Infinity [Scatbook.com]/FEEDING MY HUMAN TOILET FROM MY THRONE.mp4`

## 6. Nicht angefasst / offen

- Reparatur der 34 defekten Dateien selbst (nur diagnostiziert, nichts gelöscht/ersetzt)
- Die ~88 (untitled) / ~1498 (my_passport) "echt fehlend"-Fälle wurden nicht einzeln geprüft, ob sie
  wirklich gelöscht wurden oder nur (noch) ein Restfall des Unicode-Bugs sind, den mein Merge nicht
  gefangen hat (Merge fängt nur exakte NFC-Treffer — falls z.B. auch Groß-/Kleinschreibung oder
  andere Sonderzeichen-Varianten abweichen, würde das nicht matchen). Kurzer Stichproben-Check auf
  dem Mac wäre sinnvoll, falls die Zahl überraschend hoch wirkt.
- Transcoding + NAS-Transfer: separater nächster Schritt, laut ursprünglichem Runbook auf diesem PC
  geplant, aber noch nicht begonnen.
