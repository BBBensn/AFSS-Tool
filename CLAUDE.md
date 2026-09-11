# AFSS-Tool — Projekt-CLAUDE.md
Projekt-spezifische Ergänzung zur globalen `~/.claude/CLAUDE.md`. Ergänzt, überschreibt nie.

---

## Projekt-Basics

- Name: `afss`
- Version: `1.1.0`
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

- Aktuell: `v1.1.0`
- Kurze Historie:
  - `v1.0.0` — Grundgerüst: Datenmodell, `scan`/`resolve`/`tag`/`anonymize`/`dedupe`/`plan`/`apply`,
    Web-Dashboard, Artist-Metadaten-Editor inkl. Bio-Import
  - `v1.1.0` — `afss transcode` (Video-Normalisierung auf MP4/HEVC)

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
- ⬜ Profil `my_passport` fertig taggen (Stand zuletzt geprüft: 95 offene Ordner, nur 5 % resolved
  — mit Abstand am weitesten zurück von den drei Profilen)
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
