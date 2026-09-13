---
date_created: 2026-09-13 17:36:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-13 17:36:00
---

# v1.26.0 — Artist-Bulk-Bearbeitung, Spalten-Kontrolle (2026-09-13)

- **Vier Dummy-Artists aus der echten `config/artists.json` entfernt** (`Alpha Updated`,
  `Beta Person`, `Only Year Known`, `The_Prime_Alpha`) - Reste aus einem früheren Test-Lauf, der
  versehentlich gegen die echten Pfade statt gegen isolierte `/tmp`-Testdaten lief (0 zugeordnete
  Dateien, minimalste Tags). Backup vor dem Löschen erstellt, ebenso aus der DB (`artists` +
  `artist_aliases`) entfernt.
- **Bulk-Bearbeitung in der Artist-Liste** (`/artists/`): Checkbox pro Zeile + "Alle sichtbaren
  auswählen" im Kopf, eine Toolbox mit Feld-Dropdown (17 `default_tags`-Felder, u.a. Gender
  Identity, Sex Assigned at Birth, Occupation, Nationality) + Wert-Eingabe mit demselben
  Fetch-Autocomplete wie im Einzel-Formular + "Bei Auswahl setzen". Ersetzt den bestehenden Wert
  komplett (wie beim Einzel-Speichern), leerer Wert leert das Feld. Neue Route `POST /artists/bulk`
  in `afss/artist_editor/app.py`, neue Funktion `bulk_set_field()` in `store.py`.
- **Spalten ein-/ausblendbar + Kopfzeile fixierbar**, wie im Sortier-Studio: Menü-Button (▤) blendet
  Aliases/Gender/Nationality/Ethnicity/Videos/Aktiv einzeln aus, Pin-Button (🔓/🔒) fixiert die
  Kopfzeile beim Scrollen - beides per `localStorage` gemerkt.
- Bewusst **kein** AJAX-Swap wie im Sortier-Studio übernommen: bei nur ~220 Artists (statt
  zehntausenden Dateien) ist ein normaler POST+Redirect ausreichend und deutlich einfacher/robuster -
  Filtertext/Scroll-Position gehen nach einer Bulk-Aktion verloren, das ist bei dieser Tabellengröße
  ein akzeptabler Kompromiss.
- Neuer Error-Handler auf Blueprint-Ebene (analog Sortier-Studio) als Sicherheitsnetz gegen nackte
  500er in der neuen Bulk-Route.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
