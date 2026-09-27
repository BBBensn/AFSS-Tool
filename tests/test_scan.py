import os
import stat
import types
import unicodedata
from pathlib import Path

import pytest
import yaml

from afss.db import get_connection, init_schema
from afss.scan import apply_moved_file_matches, find_moved_file_matches, scan_profile
from afss.tagging import set_trash


def _write_profiles_yml(config_dir: Path, profile_id: str, root: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "profiles": [
            {
                "id": profile_id,
                "description": "test profile",
                "root_path": str(root),
                "enabled": True,
            }
        ]
    }
    (config_dir / "legacy_profiles.yml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _build_fake_root(root: Path) -> None:
    (root / "Artist One" / "Collection A").mkdir(parents=True)
    (root / "Artist One" / "Collection A" / "video1.mp4").write_bytes(b"x")
    (root / "Artist One" / "Collection A" / "photo1.jpg").write_bytes(b"x")
    (root / "Artist One" / "ProviderX").mkdir(parents=True)
    (root / "Artist One" / "ProviderX" / "meta.json").write_text("{}", encoding="utf-8")
    (root / "Artist Two").mkdir(parents=True)
    (root / "Artist Two" / "video2.mp4").write_bytes(b"x")


def test_scan_counts_and_folder_levels(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 4
    assert result["media_type_counts"]["video"] == 2
    assert result["media_type_counts"]["photo"] == 1
    assert result["media_type_counts"]["provider_meta"] == 1

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT folder_level1, folder_level2 FROM media_items WHERE filename = 'video1.mp4'")
    row = cur.fetchone()
    conn.close()
    assert row == ("Artist One", "Collection A")


def test_scan_skips_hidden_directories(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    (root / ".Spotlight-V100").mkdir(parents=True)
    (root / ".Spotlight-V100" / "index.dat").write_bytes(b"x")
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 4


def test_scan_skips_folders_marked_as_trash(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    (root / "$RECYCLE.BIN").mkdir(parents=True)
    (root / "$RECYCLE.BIN" / "deleted.mp4").write_bytes(b"x")
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO unresolved_folders(profile_id, folder_name, folder_level, occurrence_count, status) "
        "VALUES ('test_profile', '$RECYCLE.BIN', 1, 1, 'pending')"
    )
    unresolved_id = cur.lastrowid
    conn.commit()
    conn.close()
    set_trash(unresolved_id, db_path)

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 4


def test_scan_is_idempotent(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    result = scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE profile_id = 'test_profile'")
    count = cur.fetchone()[0]
    conn.close()

    assert count == result["total_files"] == 4


def test_rescan_preserves_manual_tagging_and_id(tmp_path):
    """Regression: scan() loeschte frueher bei JEDEM Lauf alle media_items des Profils und baute sie
    komplett neu auf (auch fuer Dateien, die sich gar nicht geaendert haben) - das hat jegliche im
    Sortier-Studio gesetzte Zuordnung (Artist, Tags, manual_override, ...) bei einem simplen Rescan
    wieder geloescht. Ein Rescan darf bestehende, unveraenderte Dateien nur in ihren dateisystem-
    abgeleiteten Spalten auffrischen, niemals in ihren Tagging-Spalten."""
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO artists(id, canonical_name) VALUES ('artist_one', 'Artist One')"
    )
    cur.execute(
        "UPDATE media_items SET artist_id = 'artist_one', tags = 'favorite', manual_override = 1, "
        "title_override = 'Custom Title' WHERE filename = 'video1.mp4'"
    )
    cur.execute("SELECT id FROM media_items WHERE filename = 'video1.mp4'")
    original_id = cur.fetchone()[0]
    conn.commit()
    conn.close()

    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, artist_id, tags, manual_override, title_override FROM media_items WHERE filename = 'video1.mp4'"
    )
    row = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE profile_id = 'test_profile'")
    total = cur.fetchone()[0]
    conn.close()

    assert row == (original_id, "artist_one", "favorite", 1, "Custom Title")
    assert total == 4  # keine Dublette angelegt


def test_scan_marks_removed_files_as_missing_without_deleting(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    (root / "Artist Two" / "video2.mp4").unlink()

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 3  # nur noch auf der Platte vorhandene Dateien
    assert result["newly_missing"] == 1
    assert result["missing_total"] == 1

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE profile_id = 'test_profile'")
    total = cur.fetchone()[0]
    cur.execute("SELECT missing_since FROM media_items WHERE filename = 'video2.mp4'")
    missing_since = cur.fetchone()[0]
    cur.execute("SELECT missing_since FROM media_items WHERE filename = 'video1.mp4'")
    still_present = cur.fetchone()[0]
    conn.close()

    assert total == 4  # Zeile bleibt erhalten, wird nicht geloescht
    assert missing_since is not None
    assert still_present is None


def test_scan_clears_missing_since_when_file_reappears(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    video_path = root / "Artist Two" / "video2.mp4"
    video_path.unlink()
    scan_profile("test_profile", config_dir, db_path)
    video_path.write_bytes(b"x")

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["missing_total"] == 0
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT missing_since FROM media_items WHERE filename = 'video2.mp4'")
    missing_since = cur.fetchone()[0]
    conn.close()
    assert missing_since is None


def test_scan_does_not_advance_missing_since_on_repeated_scans(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    (root / "Artist Two" / "video2.mp4").unlink()
    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE media_items SET missing_since = '2020-01-01T00:00:00' WHERE filename = 'video2.mp4'")
    conn.commit()
    conn.close()

    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT missing_since FROM media_items WHERE filename = 'video2.mp4'")
    missing_since = cur.fetchone()[0]
    conn.close()
    assert missing_since == "2020-01-01T00:00:00"


def test_scan_new_file_added_alongside_existing_tagged_files(tmp_path):
    """Der eigentliche Anlassfall: neue Clips kommen dazu, der Rest ist schon getaggt - ein Rescan
    darf nur die neue Datei ergaenzen, den Rest unangetastet lassen."""
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO artists(id, canonical_name) VALUES ('artist_one', 'Artist One')")
    cur.execute("UPDATE media_items SET artist_id = 'artist_one', manual_override = 1 WHERE filename = 'video1.mp4'")
    conn.commit()
    conn.close()

    (root / "Artist Three").mkdir(parents=True)
    (root / "Artist Three" / "new_clip.mp4").write_bytes(b"x")

    result = scan_profile("test_profile", config_dir, db_path)

    assert result["total_files"] == 5
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT artist_id, manual_override FROM media_items WHERE filename = 'video1.mp4'")
    preserved = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE filename = 'new_clip.mp4'")
    new_count = cur.fetchone()[0]
    conn.close()
    assert preserved == ("artist_one", 1)
    assert new_count == 1


def test_scan_skips_missing_marking_when_walk_has_read_errors(tmp_path):
    """Regression: os.walk() schluckt Lese-Fehler pro Verzeichnis standardmaessig - bei einer kurz
    hakenden USB/SMB-Verbindung wuerde ein ganzer, weiterhin vorhandener Unterordner stillschweigend
    uebersprungen und seine Dateien faelschlich als 'fehlend' markiert. Ein Scan mit Lese-Fehlern
    darf daher gar keine neuen missing_since-Markierungen setzen."""
    if os.geteuid() == 0:
        pytest.skip("chmod-basierte Zugriffsverweigerung wirkt nicht als root")

    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)

    blocked_dir = root / "Artist One" / "Collection A"
    original_mode = blocked_dir.stat().st_mode
    blocked_dir.chmod(0o000)
    try:
        result = scan_profile("test_profile", config_dir, db_path)
    finally:
        blocked_dir.chmod(stat.S_IMODE(original_mode))

    assert result["walk_errors"]
    assert result["newly_missing"] == 0

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE missing_since IS NOT NULL")
    still_missing = cur.fetchone()[0]
    conn.close()
    assert still_missing == 0  # nichts wurde faelschlich als fehlend markiert


def test_find_moved_file_matches_detects_unique_rename(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO artists(id, canonical_name) VALUES ('artist_one', 'Artist One')"
    )
    conn.execute(
        "UPDATE media_items SET artist_id = 'artist_one', tags = 'favorite' WHERE filename = 'video1.mp4'"
    )
    conn.commit()
    conn.close()

    # Ordner-Umbenennung simulieren: "Collection A" -> "Collection Renamed"
    (root / "Artist One" / "Collection A").rename(root / "Artist One" / "Collection Renamed")

    scan_profile("test_profile", config_dir, db_path)
    matches = find_moved_file_matches("test_profile", db_path)

    video1_match = next(m for m in matches if m["filename"] == "video1.mp4")
    assert video1_match["missing_rel_path"] == "Artist One/Collection A/video1.mp4"
    assert video1_match["present_rel_path"] == "Artist One/Collection Renamed/video1.mp4"


def test_find_moved_file_matches_ignores_ambiguous_same_name_and_size(tmp_path):
    """Generische Dateinamen (z.B. '001.jpg') kommen in mehreren, voellig unabhaengigen Ordnern vor
    und koennen zufaellig sogar dieselbe Groesse haben - ein Treffer wird nur vorgeschlagen, wenn
    Name UND Groesse EINDEUTIG sind (genau ein Kandidat auf jeder Seite), sonst lieber gar kein
    Vorschlag als eine falsche Zusammenfuehrung zweier unterschiedlicher Dateien."""
    root = tmp_path / "fake_root"
    (root / "SetA").mkdir(parents=True)
    (root / "SetA" / "001.jpg").write_bytes(b"x" * 100)
    (root / "SetB").mkdir(parents=True)
    (root / "SetB" / "001.jpg").write_bytes(b"y" * 100)  # gleicher Name, gleiche Groesse, anderer Inhalt
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    # Nur SetA wird umbenannt - SetB/001.jpg bleibt unangetastet stehen und sorgt so fuer eine
    # zweideutige Situation: nach dem Rescan gibt es ZWEI "present" 001.jpg mit Groesse 100.
    (root / "SetA").rename(root / "SetA_renamed")
    scan_profile("test_profile", config_dir, db_path)

    matches = find_moved_file_matches("test_profile", db_path)

    assert matches == []  # zwei gleich grosse "present" Kandidaten -> nicht eindeutig, kein Vorschlag


def test_apply_moved_file_matches_fills_blanks_and_removes_old_row(tmp_path):
    root = tmp_path / "fake_root"
    _build_fake_root(root)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    conn = get_connection(db_path)
    conn.execute("INSERT INTO artists(id, canonical_name) VALUES ('artist_one', 'Artist One')")
    conn.execute(
        "UPDATE media_items SET artist_id = 'artist_one', tags = 'favorite', manual_override = 1 "
        "WHERE filename = 'video1.mp4'"
    )
    old_id = conn.execute("SELECT id FROM media_items WHERE filename = 'video1.mp4'").fetchone()[0]
    conn.commit()
    conn.close()

    (root / "Artist One" / "Collection A").rename(root / "Artist One" / "Collection Renamed")
    scan_profile("test_profile", config_dir, db_path)
    matches = find_moved_file_matches("test_profile", db_path)

    merged = apply_moved_file_matches(matches, db_path)

    assert merged == len(matches)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT artist_id, tags, manual_override, missing_since FROM media_items WHERE filename = 'video1.mp4'"
    )
    row = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE id = ?", (old_id,))
    old_row_gone = cur.fetchone()[0] == 0
    conn.close()

    assert row == ("artist_one", "favorite", 1, None)
    assert old_row_gone


def test_scan_stores_filenames_normalized_to_nfc(tmp_path):
    """Regression v1.31.1: macOS/APFS speichert Dateinamen mit Akzenten/Umlauten/kyrillischen
    Zeichen exakt so, wie sie geschrieben wurden (hier bewusst zerlegt/NFD angelegt) - Windows
    liefert dieselben logischen Namen beim eigenen Scan zusammengesetzt (NFC). scan() muss
    unabhängig von der Rohform des Dateisystems konsequent NFC speichern, sonst matcht der
    Upsert-Unique-Key (profile_id, rel_path) eine vom anderen Betriebssystem gescannte Zeile nicht."""
    root = tmp_path / "fake_root"
    root.mkdir(parents=True)
    nfd_name = unicodedata.normalize("NFD", "café.mp4")
    (root / nfd_name).write_bytes(b"x")
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT filename, rel_path FROM media_items WHERE profile_id = 'test_profile'")
    filename, rel_path = cur.fetchone()
    conn.close()

    assert filename == unicodedata.normalize("NFC", filename)
    assert rel_path == unicodedata.normalize("NFC", rel_path)
    assert filename == "café.mp4"  # zusammengesetzte Form, nicht die zerlegte Rohform vom Dateisystem


def test_rescan_matches_same_file_across_nfd_and_nfc_forms(tmp_path):
    """Kern-Regressionstest fuer den v1.31.1-Bug: eine Datei, die einmal in zerlegter (NFD) und
    einmal in zusammengesetzter (NFC) Form gescannt wird (genau das, was beim Wechsel macOS<->
    Windows fuer dieselbe physische Datei passiert), darf NICHT als zwei verschiedene Dateien
    behandelt werden - keine Dublette, keine faelschliche missing_since-Markierung, Tagging bleibt
    an derselben Zeile (gleiche id) erhalten."""
    root = tmp_path / "fake_root"
    root.mkdir(parents=True)
    nfd_name = unicodedata.normalize("NFD", "café.mp4")
    nfc_name = unicodedata.normalize("NFC", "café.mp4")
    (root / nfd_name).write_bytes(b"x" * 100)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    scan_profile("test_profile", config_dir, db_path)
    conn = get_connection(db_path)
    conn.execute("INSERT INTO artists(id, canonical_name) VALUES ('artist_one', 'Artist One')")
    conn.execute(
        "UPDATE media_items SET artist_id = 'artist_one', tags = 'favorite', manual_override = 1 "
        "WHERE profile_id = 'test_profile'"
    )
    original_id = conn.execute("SELECT id FROM media_items WHERE profile_id = 'test_profile'").fetchone()[0]
    conn.commit()
    conn.close()

    # Simuliert einen Scan auf einem anderen Betriebssystem (z.B. Windows), das denselben Namen in
    # zusammengesetzter Form liefert - dieselbe physische Datei, andere Rohbytes im Dateinamen.
    (root / nfd_name).unlink()
    (root / nfc_name).write_bytes(b"x" * 100)

    result = scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM media_items WHERE profile_id = 'test_profile'")
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT id, artist_id, tags, manual_override, missing_since FROM media_items WHERE profile_id = 'test_profile'"
    )
    row = cur.fetchone()
    conn.close()

    assert total == 1  # keine Dublette
    assert row == (original_id, "artist_one", "favorite", 1, None)  # gleiche id, Tags erhalten, nicht "fehlend"
    assert result["newly_missing"] == 0


def test_scan_keeps_file_size_when_creation_timestamp_is_invalid(tmp_path, monkeypatch):
    """Regression v1.31.1: manche NTFS-Dateien liefern ein kaputtes/leeres st_ctime (Windows-
    FILETIME-Nullwert-Sentinel, Jahr 1601 -> ValueError bei datetime.fromtimestamp). Groesse und
    mtime muessen davon unabhaengig trotzdem korrekt erfasst werden - vorher hat ein gemeinsames
    try/except um alle drei Werte auch die eigentlich intakte Groesse mit verworfen."""
    root = tmp_path / "fake_root"
    root.mkdir(parents=True)
    (root / "video.mp4").write_bytes(b"x" * 500)
    config_dir = tmp_path / "config"
    _write_profiles_yml(config_dir, "test_profile", root)
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    real_stat = Path.stat

    def fake_stat(self, *args, **kwargs):
        result = real_stat(self, *args, **kwargs)
        if self.name == "video.mp4":
            return types.SimpleNamespace(
                st_size=result.st_size,
                st_ctime=-99999999999999,  # ausserhalb des von datetime darstellbaren Bereichs
                st_mtime=result.st_mtime,
            )
        return result

    monkeypatch.setattr(Path, "stat", fake_stat)

    scan_profile("test_profile", config_dir, db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT size_bytes, fs_created_at, fs_modified_at FROM media_items WHERE filename = 'video.mp4'"
    )
    size_bytes, fs_created_at, fs_modified_at = cur.fetchone()
    conn.close()

    assert size_bytes == 500  # bleibt trotz kaputtem ctime erhalten
    assert fs_created_at is None  # konnte nicht konvertiert werden
    assert fs_modified_at is not None  # unabhaengig davon weiterhin erfasst
