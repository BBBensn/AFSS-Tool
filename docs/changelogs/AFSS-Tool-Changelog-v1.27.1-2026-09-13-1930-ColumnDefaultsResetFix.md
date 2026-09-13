---
date_created: 2026-09-13 19:30:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-13 19:30:00
---

# v1.27.1 — Bugfix: Spalten-Vorbelegung nach v1.27.0 (2026-09-13)

- Nach v1.27.0 (24 statt 6 Spalten) waren beim nächsten Laden plötzlich ALLE Spalten aufgeklappt
  statt nur der bisherigen sechs Standard-Spalten. Ursache: der bestehende `localStorage`-Eintrag
  stand noch auf `[]` (nichts ausgeblendet) aus der Zeit, als es nur die 6 Spalten gab - v1.27.0 hat
  diesen leeren Wert unverändert übernommen und ihn auf alle 24 Spalten angewendet, statt die 18
  neuen Spalten wie vorgesehen eingeklappt zu starten.
- Fix: neuer `localStorage`-Key (`afss_artist_hidden_columns_v2`) - der alte, jetzt nicht mehr
  passende Wert wird ignoriert, es wird sauber mit der vorgesehenen Standardansicht (Aliases,
  Gender, Nationality, Ethnicity, Videos, Aktiv sichtbar, Rest eingeklappt) neu gestartet.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
