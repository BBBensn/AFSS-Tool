---
date_created: 2026-09-13 16:02:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-13 16:02:00
---

# v1.23.0 — Einheitliche Navigation über alle Seiten (2026-09-13)

Dritter von vier Schritten des Artist-/Tag-Editor-Ausbaus (siehe Plan
`ok-ich-bin-seit-humming-badger.md`).

- **Gleiche Nav-Leiste auf allen fünf Seiten** (Dashboard, Sortier-Studio, Artist-Liste,
  Artist-Formular, Tag-Editor): Dashboard / Sortier-Studio / Artists / Tags, aktive Seite optisch
  markiert. Ersetzt die bisherigen uneinheitlichen Rück-Links (`← Dashboard` im Sortier-Studio,
  `← Übersicht` im Artist-Formular, gar keiner in der Artist-Liste) - von überall kommt man jetzt
  mit einem Klick zu jeder anderen Seite, nicht nur eine Ebene zurück.
- Bewusst **kein** gemeinsames Jinja-Base-Template (das Projekt hat strukturell keins, jede Seite
  bleibt ein eigenständiges HTML-Dokument) - stattdessen derselbe HTML/CSS-Schnipsel an fünf Stellen
  eingefügt. Links sind feste relative Pfade (`/`, `/sort/all/`, `/artists/`, `/tags/`) statt
  `url_for(...)`, damit die Leiste unverändert funktioniert, egal ob eine Seite über
  `afss dashboard` oder eigenständig (`afss sort`/`afss artists`/`afss tags`) läuft - jeder
  Blueprint mountet unter demselben `url_prefix`, ob standalone oder im Dashboard registriert.
- Die per-Profil Tag-Queue (`/tag/<profile_id>/`) bleibt bewusst außerhalb dieser globalen Leiste,
  da es dafür (anders als beim Sortier-Studio mit `profile_id="all"`) keinen sinnvollen
  profilunabhängigen Standard-Link gibt - weiterhin nur pro Profil im Dashboard verlinkt.

**Noch offen** (Schritt 4): leichter visueller Politur-Pass (Farb-/Spacing-Angleichung an das
Sortier-Studio-Aussehen).

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
