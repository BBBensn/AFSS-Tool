---
date_created: 2026-09-13 15:44:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-13 15:44:00
---

# v1.21.0 — Artist-Editor: Autocomplete, ausgebaute Liste (2026-09-13)

Erster von vier Schritten, um den Artist-Editor auf das Bedienniveau des Sortier-Studios zu heben
(siehe Plan `ok-ich-bin-seit-humming-badger.md`).

- **Autocomplete für sieben Freitext-Felder**: Nationality, Ethnicity, Geburtsort (Stadt/Bundesland/
  Land-ISO), Bra Size, Artist Tags, Occupation, Piercings zeigen jetzt Vorschläge aus bereits über
  andere Artists vergebenen Werten (neue `distinct_field_values()` in `store.py`, Route
  `GET /artists/field-values`, feste Feld-Allow-Liste). Gleiches Debounce+Dropdown-Muster wie im
  Sortier-Studio, portiert statt neu erfunden. Verhindert Nah-Duplikate durch Groß-/Kleinschreibung
  oder Leerzeichen-Varianten, die bisher von Hand nachkorrigiert werden mussten. Die schon
  vorhandenen `<datalist>`-Felder mit echten Festwerten (Gender Identity, Body Type, etc.) bleiben
  unverändert.
- **Artist-Liste ausgebaut**: Text-Filter über Name/Alias/Nationality/Ethnicity, drei neue Spalten
  (Nationality, Ethnicity, Videos), alle Spalten per Klick auf-/absteigend sortierbar (gleiches
  Muster wie die klickbaren Tabellen-Header im Sortier-Studio).

**Noch offen** (Schritte 2-4 dieses Auftrags): neuer Tag-Editor, einheitliche Navigation über alle
Seiten, leichter visueller Politur-Pass.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
