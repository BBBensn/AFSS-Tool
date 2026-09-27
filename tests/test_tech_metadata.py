import shutil
import subprocess

import pytest

from afss.db import get_connection, init_schema
from afss.tech_metadata import collect_technical_metadata, probe_technical_info

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe nicht installiert",
)


def _make_test_clip(path, width=64, height=48, duration=1, fps=10):
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size={width}x{height}:rate={fps}",
            "-f", "lavfi", "-i", f"sine=duration={duration}",
            "-c:v", "libx264", "-c:a", "aac",
            str(path),
        ],
        capture_output=True, check=True,
    )


def _seed_profile(cur, profile_id="p1"):
    cur.execute(
        "INSERT OR IGNORE INTO profiles(id, root_path, created_at) VALUES (?, '/tmp', '2020-01-01')",
        (profile_id,),
    )


def _insert_video_item(cur, path, profile_id="p1"):
    _seed_profile(cur, profile_id)
    cur.execute(
        """
        INSERT INTO media_items(profile_id, path, rel_path, filename, ext, media_type, scanned_at)
        VALUES (?, ?, ?, ?, '.mp4', 'video', '2020-01-01')
        """,
        (profile_id, str(path), path.name, path.name),
    )
    return cur.lastrowid


def test_probe_technical_info_reads_resolution_and_codec(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_test_clip(clip, width=128, height=96, fps=25)

    info = probe_technical_info(clip)

    assert info["width"] == 128
    assert info["height"] == 96
    assert info["video_codec"] == "h264"
    assert info["frame_rate"] == 25.0
    assert info["audio_codec"] == "aac"
    assert info["duration_seconds"] is not None


def test_probe_technical_info_returns_none_for_unreadable_file(tmp_path):
    junk = tmp_path / "not_a_video.mp4"
    junk.write_bytes(b"this is not a real video file")

    assert probe_technical_info(junk) is None


def test_collect_technical_metadata_stores_row_per_video(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    clip = tmp_path / "clip.mp4"
    _make_test_clip(clip)

    conn = get_connection(db_path)
    cur = conn.cursor()
    item_id = _insert_video_item(cur, clip)
    conn.commit()
    conn.close()

    result = collect_technical_metadata("p1", db_path)

    assert result == {"profile_id": "p1", "candidates": 1, "probed": 1, "failed": []}
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT width, height, video_codec FROM media_technical_info WHERE media_item_id = ?", (item_id,))
    row = cur.fetchone()
    conn.close()
    assert row == (64, 48, "h264")


def test_collect_technical_metadata_skips_already_probed_unless_forced(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    clip = tmp_path / "clip.mp4"
    _make_test_clip(clip)

    conn = get_connection(db_path)
    cur = conn.cursor()
    _insert_video_item(cur, clip)
    conn.commit()
    conn.close()

    first = collect_technical_metadata("p1", db_path)
    second = collect_technical_metadata("p1", db_path)
    forced = collect_technical_metadata("p1", db_path, force=True)

    assert first["probed"] == 1
    assert second["candidates"] == 0  # bereits geprobt, nichts mehr zu tun
    assert forced["candidates"] == 1  # force ignoriert den bisherigen Fortschritt


def test_collect_technical_metadata_reports_missing_source(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    _insert_video_item(cur, tmp_path / "gone.mp4")
    conn.commit()
    conn.close()

    result = collect_technical_metadata("p1", db_path)

    assert result["probed"] == 0
    assert len(result["failed"]) == 1
    assert "fehlt" in result["failed"][0]["reason"]


def test_collect_technical_metadata_reports_unreadable_file(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"not a real video")

    conn = get_connection(db_path)
    cur = conn.cursor()
    _insert_video_item(cur, junk)
    conn.commit()
    conn.close()

    result = collect_technical_metadata("p1", db_path)

    assert result["probed"] == 0
    assert len(result["failed"]) == 1
