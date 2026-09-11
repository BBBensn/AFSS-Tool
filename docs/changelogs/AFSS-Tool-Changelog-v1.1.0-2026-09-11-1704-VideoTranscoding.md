---
date_created: 2026-09-11 17:04:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-11 17:04:00
---

# v1.1.0 — Video-Transcoding auf einheitliches Format (2026-09-11)
- Neuer Befehl `afss transcode --profile <id>` normalisiert bereits applied Videos auf MP4/HEVC
- Encoder-Erkennung zur Laufzeit (VideoToolbox/NVENC/QSV/libx265), portabel zwischen Mac und
  Windows-PC (RTX 5070) ohne Codeänderung — Repo kann unverändert dort geklont werden
- Verifikation per Dauer-Abgleich (Hash-Vergleich unmöglich, da Transcoding die Bytes bewusst
  ändert); bereits im Zielformat befindliche Dateien werden übersprungen (idempotent)
- `--delete-source` löscht alte Vor-Transcode-Dateien erst nach Verifikation und expliziter
  Bestätigung, analog zu `apply --delete-source`
- Neue Spalten `transcoded_path`/`transcoded_at`/`transcode_verified` in `media_items`,
  bestehende `afss.db` (15.635 Zeilen) migriert ohne Datenverlust
- Bewusst kein Dashboard-Button — Transcoding kann je nach Bibliotheksgröße Stunden bis Tage
  dauern, ungeeignet für eine synchrone Flask-Anfrage
