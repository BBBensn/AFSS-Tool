---
date_created: 2026-09-13 17:07:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-13 17:07:00
---

# v1.25.0 — Gender/Sex/Orientation-Felder überarbeitet (2026-09-13)

- **`sex_assigned_at_birth`** um `intersex` ergänzt (bisher nur female/male - echte Lücke).
- **`gender_identity`**: `trans` als Wert entfernt, `non_binary` bleibt. Grund: eine Prüfung der
  echten Daten (225 Artists, nur Aggregat-Zahlen betrachtet, keine Namen) zeigte, dass "trans" als
  eigener Wert nie benutzt wurde - stattdessen wird trans-Sein bereits korrekt und ohne Informations-
  verlust über die Kombination beider Felder ausgedrückt (z.B. `gender_identity=female` +
  `sex_assigned_at_birth=male` = trans Frau, 11 bestehende Einträge genau so). Ein eigener
  `trans`-Wert für `gender_identity` hätte das *welches* Geschlecht (Frau vs. Mann) verschluckt -
  daher bewusst **nicht** wie ursprünglich vorgeschlagen zu einer cis/trans-Kategorie umgebaut,
  sondern die bestehende, bereits verlustfreie Modellierung beibehalten und nur die echte Lücke
  (intersex) geschlossen. Ein Hinweistext im Formular erklärt das jetzt direkt an der Stelle.
- **Neues Feld `sexual_orientation`** (heterosexual/homosexual/pansexual, frei erweiterbar wie die
  anderen `<datalist>`-Felder) - bei allen 225 bestehenden Artists mit `pansexual` vorbelegt
  (`config/artists.json`, vorher per Backup gesichert).
- Keine Datenmigration für gender_identity/sex_assigned_at_birth nötig - die bestehenden Werte
  passen bereits ins überarbeitete Modell.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
