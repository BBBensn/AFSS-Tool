import shutil
import subprocess

import pytest

from afss.db import get_connection, init_schema
from afss.transcode import (
    _detect_encoder,
    _ffprobe_info,
    _is_already_target_format,
    delete_pretranscode_sources,
    transcode_profile,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe nicht installiert",
)


def _make_test_clip(path, codec="libx264", duration=1):
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=64x64:rate=10",
            "-f", "lavfi", "-i", f"sine=duration={duration}",
            "-c:v", codec, "-c:a", "aac",
            str(path),
        ],
        capture_output=True, check=True,
    )


def _seed_profile(cur, profile_id="p1"):
    cur.execute(
        "INSERT OR IGNORE INTO profiles(id, root_path, created_at) VALUES (?, '/tmp', '2020-01-01')",
        (profile_id,),
    )


def _insert_applied_item(cur, target_path, profile_id="p1"):
    _seed_profile(cur, profile_id)
    cur.execute(
        """
        INSERT INTO media_items(
            profile_id, path, rel_path, filename, ext, media_type,
            target_path, verified, scanned_at
        ) VALUES (?, ?, ?, ?, ?, 'video', ?, 1, '2020-01-01')
        """,
        (profile_id, str(target_path), target_path.name, target_path.name, target_path.suffix, str(target_path)),
    )
    return cur.lastrowid


def test_detect_encoder_returns_known_value():
    encoder = _detect_encoder()
    assert encoder in {"hevc_videotoolbox", "hevc_nvenc", "hevc_qsv", "libx265"}


def test_ffprobe_info_reads_codec_and_duration(tmp_path):
    clip = tmp_path / "clip.mkv"
    _make_test_clip(clip, codec="libx264", duration=1)

    info = _ffprobe_info(clip)

    assert info["codec_name"] == "h264"
    assert info["duration"] is not None
    assert 0.8 <= info["duration"] <= 1.5


def test_ffprobe_info_missing_file_returns_none(tmp_path):
    info = _ffprobe_info(tmp_path / "does_not_exist.mp4")
    assert info == {"codec_name": None, "duration": None}


def test_is_already_target_format():
    assert _is_already_target_format(__import__("pathlib").Path("x.mp4"), {"codec_name": "hevc"}) is True
    assert _is_already_target_format(__import__("pathlib").Path("x.mkv"), {"codec_name": "hevc"}) is False
    assert _is_already_target_format(__import__("pathlib").Path("x.mp4"), {"codec_name": "h264"}) is False


def test_transcode_profile_converts_to_mp4_hevc(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    clip = tmp_path / "video.mkv"
    _make_test_clip(clip, codec="libx264", duration=1)

    conn = get_connection(db_path)
    cur = conn.cursor()
    item_id = _insert_applied_item(cur, clip)
    conn.commit()
    conn.close()

    result = transcode_profile("p1", db_path)

    assert result["transcoded"] == 1
    assert result["failed"] == []

    new_path = tmp_path / "video.mp4"
    assert new_path.exists()
    assert clip.exists()  # alte Datei bleibt liegen - Löschen ist ein separater, expliziter Schritt

    info = _ffprobe_info(new_path)
    assert info["codec_name"] == "hevc"

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT transcoded_path, transcode_verified FROM media_items WHERE id = ?", (item_id,))
    transcoded_path, transcode_verified = cur.fetchone()
    assert transcoded_path == str(new_path)
    assert transcode_verified == 1
    conn.close()


def test_transcode_profile_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    clip = tmp_path / "video.mkv"
    _make_test_clip(clip, codec="libx264", duration=1)

    conn = get_connection(db_path)
    cur = conn.cursor()
    _insert_applied_item(cur, clip)
    conn.commit()
    conn.close()

    first = transcode_profile("p1", db_path)
    second = transcode_profile("p1", db_path)

    assert first["transcoded"] == 1
    assert second["candidates"] == 0  # bereits transcode_verified=1, kein Kandidat mehr


def test_transcode_profile_skips_already_correct_format(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    clip = tmp_path / "video.mp4"
    _make_test_clip(clip, codec="libx265", duration=1)

    conn = get_connection(db_path)
    cur = conn.cursor()
    item_id = _insert_applied_item(cur, clip)
    conn.commit()
    conn.close()

    result = transcode_profile("p1", db_path)

    assert result["already_correct"] == 1
    assert result["transcoded"] == 0

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT transcoded_path, transcode_verified FROM media_items WHERE id = ?", (item_id,))
    transcoded_path, transcode_verified = cur.fetchone()
    assert transcoded_path == str(clip)
    assert transcode_verified == 1
    conn.close()


def test_transcode_profile_flags_missing_file(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    missing = tmp_path / "gone.mkv"
    conn = get_connection(db_path)
    cur = conn.cursor()
    _insert_applied_item(cur, missing)
    conn.commit()
    conn.close()

    result = transcode_profile("p1", db_path)

    assert result["transcoded"] == 0
    assert len(result["failed"]) == 1
    assert "Datei fehlt" in result["failed"][0]["reason"]


def test_delete_pretranscode_sources_deletes_old_file_when_extension_changed(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    clip = tmp_path / "video.mkv"
    _make_test_clip(clip, codec="libx264", duration=1)

    conn = get_connection(db_path)
    cur = conn.cursor()
    _insert_applied_item(cur, clip)
    conn.commit()
    conn.close()

    transcode_profile("p1", db_path)
    new_path = tmp_path / "video.mp4"
    assert clip.exists() and new_path.exists()  # beide liegen noch nebeneinander

    result = delete_pretranscode_sources("p1", db_path)

    assert result["deleted"] == 1
    assert not clip.exists()
    assert new_path.exists()


def test_delete_pretranscode_sources_skips_when_same_file(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    clip = tmp_path / "video.mp4"
    _make_test_clip(clip, codec="libx265", duration=1)

    conn = get_connection(db_path)
    cur = conn.cursor()
    _insert_applied_item(cur, clip)
    conn.commit()
    conn.close()

    transcode_profile("p1", db_path)  # bereits korrektes Format -> transcoded_path == target_path
    result = delete_pretranscode_sources("p1", db_path)

    assert result["deleted"] == 0
    assert result["skipped_same_file"] == 1
    assert clip.exists()
