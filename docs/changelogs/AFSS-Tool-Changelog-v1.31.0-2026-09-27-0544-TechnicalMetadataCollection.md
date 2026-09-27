---
date_created: 2026-09-27 05:44:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-27 05:44:00
---

# v1.31.0 — Technische Video-Metadaten sammeln (2026-09-27)

- Neu `afss/tech_metadata.py::collect_technical_metadata()` + CLI `afss collect-metadata --profile
  <p> [--force]`: ein ffprobe-Aufruf pro Video sammelt Auflösung, Video-/Audio-Codec, Video-/Audio-/
  Gesamt-Bitrate, Framerate, Audiokanäle/-Samplerate, Dauer und Container-Format in eine neue Tabelle
  `media_technical_info` (1:1 zu `media_items`).
- Bewusst **vor** `transcode()` gedacht, nicht danach oder gleichzeitig: nach dem Transcoding ist
  alles auf ein einheitliches Format normalisiert - genau die Unterschiede in Auflösung/Bitrate/
  Codec, die man später zum Duplikat-Erkennen bzw. zum Auffinden der höherqualitativen Version
  zweier Kandidaten braucht, wären dann weg.
- Läuft unabhängig von `apply`/`transcode` direkt gegen die aktuelle Quelldatei (`media_items.path`)
  - kein Zwischenschritt nötig, direkt nach `scan`/`resolve` einsetzbar.
- Ohne `--force` werden bereits geprobte Dateien übersprungen (Upsert je `media_item_id`) - macht
  einen langen, unbeaufsichtigten Lauf über tausende Videos sicher fortsetzbar nach einem Abbruch;
  committet außerdem alle 50 Dateien statt nur am Ende, aus demselben Grund.
- 6 neue Tests (echte per ffmpeg generierte Testclips, wie schon bei `transcode_profile`).

**Hinweis:** noch nicht gegen echte Daten gelaufen - der Plan war ein Nachtlauf, wurde aber auf den
PC verschoben (Nutzer-Entscheidung: PC ist stationär, liest die Platten nativ ohne NTFS-Unsicherheiten
über macOS). `media_items.path` ist absolut und OS-spezifisch - vor dem ersten Lauf auf einer neuen
Maschine erst `legacy_profiles.yml`s `root_path` anpassen und neu scannen (sicher dank v1.29.0s
additivem Scan), sonst findet `collect-metadata` keine der Quelldateien.
