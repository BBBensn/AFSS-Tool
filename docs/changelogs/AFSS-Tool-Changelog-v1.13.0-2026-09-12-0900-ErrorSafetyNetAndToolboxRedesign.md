---
date_created: 2026-09-12 09:00:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 09:00:00
---

# v1.13.0 — Sortier-Studio: Fehler-Sicherheitsnetz, Toolbox nach Design-Vorlage (2026-09-12)

- **Zusätzliches Sicherheitsnetz gegen "Aktion fehlgeschlagen"**: die try/excepts aus v1.12.0 fangen
  Fehler in der Aktions-Logik ab, aber ein Fehler beim anschließenden Neu-Rendern der Seite
  (`_render_page()`, z.B. nach einer erfolgreichen Aktion) lief bisher noch daran vorbei und landete
  wieder als nackter 500er. Ein blueprint-weiter Error-Handler fängt jetzt jeden verbleibenden
  Fehler in `/sort/*` ab und zeigt ihn als Flash-Hinweis - damit bleibt keine Lücke mehr offen, durch
  die ein Fehler ungefiltert durchrutschen könnte. `/search` antwortet bei einem Fehler jetzt mit
  einer leeren Trefferliste statt einer HTML-Fehlerseite (die Autocomplete erwartet JSON).
  Zusätzlich: gegen ~16.000 synthetische Dateien über 4 Profile mit Unicode-Namen, Kommas/
  Anführungszeichen in Titeln/Collections, neu angelegten Artists/Providern und Artists, die nur in
  `artists.json` (nicht in der DB) existieren, getestet - alle Bulk-Aktionen liefen fehlerfrei durch.
  **Falls der Fehler trotzdem wieder auftritt**: das Terminal, in dem `afss dashboard` läuft, zeigt
  bei einem echten Python-Fehler immer den vollständigen Traceback (auch ohne Debug-Modus) - dieser
  Text ist der schnellste Weg zur genauen Ursache.
- **Toolbox neu gestaltet** nach einer vom Nutzer bereitgestellten Design-Vorlage: zweizeiliges
  Layout (Ansicht/Artist/Provider/Collection/Status/Co-Artist oben, Tags/Verwaltung + "Alles setzen"
  unten), einheitliche Strich-Icons (Haken/Plus/X/Speichern/Rückgängig/Flagge/Tag/Person+) statt der
  bisherigen gefüllten Material-Icons, größere Card-Abstände, Eingabefeld über den zugehörigen
  Icon-Buttons statt in derselben Zeile, eigener Chevron für Selects, "Alles setzen" als auffälliger
  Primärbutton unten rechts auf gleicher Zeile wie Tags/Verwaltung.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
