import datetime
import json
import subprocess
from pathlib import Path

from afss.db import get_connection

_ENCODER_PRIORITY = ["hevc_videotoolbox", "hevc_nvenc", "hevc_qsv"]
_FALLBACK_ENCODER = "libx265"

_ENCODER_QUALITY_ARGS = {
    "hevc_videotoolbox": ["-q:v", "65"],
    "hevc_nvenc": ["-rc", "vbr", "-cq", "22", "-preset", "p5"],
    "hevc_qsv": ["-global_quality", "22"],
    "libx265": ["-crf", "22", "-preset", "medium"],
}

DURATION_TOLERANCE_SECONDS = 2.0
DURATION_TOLERANCE_RATIO = 0.01


def _detect_encoder() -> str:
    """Prüft die lokale ffmpeg-Build-Konfiguration auf verfügbare Hardware-Encoder.
    Funktioniert identisch auf macOS (VideoToolbox), Windows/Nvidia (NVENC), Intel (QSV) -
    hängt nur davon ab, womit dieses ffmpeg gebaut wurde, kein Extra-Package nötig."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return _FALLBACK_ENCODER

    for encoder in _ENCODER_PRIORITY:
        if encoder in result.stdout:
            return encoder
    return _FALLBACK_ENCODER


def _quality_args(encoder: str, crf: int | None) -> list[str]:
    if crf is None:
        return _ENCODER_QUALITY_ARGS.get(encoder, _ENCODER_QUALITY_ARGS[_FALLBACK_ENCODER])
    if encoder == "hevc_videotoolbox":
        return ["-q:v", str(crf)]
    if encoder == "hevc_nvenc":
        return ["-rc", "vbr", "-cq", str(crf), "-preset", "p5"]
    if encoder == "hevc_qsv":
        return ["-global_quality", str(crf)]
    return ["-crf", str(crf), "-preset", "medium"]


def _ffprobe_info(path: Path) -> dict:
    """Liefert {'codec_name': str|None, 'duration': float|None} - None bei nicht lesbaren Dateien."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {"codec_name": None, "duration": None}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"codec_name": None, "duration": None}

    streams = data.get("streams", [])
    codec_name = streams[0].get("codec_name") if streams else None
    duration_str = data.get("format", {}).get("duration")
    duration = float(duration_str) if duration_str else None
    return {"codec_name": codec_name, "duration": duration}


def _is_already_target_format(path: Path, info: dict) -> bool:
    return info.get("codec_name") == "hevc" and path.suffix.lower() == ".mp4"


def _durations_match(original: float | None, transcoded: float | None) -> bool:
    if original is None or transcoded is None:
        return False
    tolerance = max(DURATION_TOLERANCE_SECONDS, original * DURATION_TOLERANCE_RATIO)
    return abs(original - transcoded) <= tolerance


def transcode_profile(
    profile_id: str,
    db_path: Path | None = None,
    encoder: str | None = None,
    crf: int | None = None,
) -> dict:
    """Transcodiert bereits applied Videos (target_path gesetzt, verified=1) auf MP4/HEVC.
    Bereits passende Dateien werden übersprungen. Verifiziert per Dauer-Abgleich (kein
    Hash-Vergleich möglich - die Bytes ändern sich beim Transcoding absichtlich)."""
    resolved_encoder = encoder or _detect_encoder()
    quality_args = _quality_args(resolved_encoder, crf)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, target_path FROM media_items
        WHERE profile_id = ? AND media_type = 'video' AND target_path IS NOT NULL
              AND verified = 1 AND transcode_verified = 0
        """,
        (profile_id,),
    )
    rows = cur.fetchall()

    now_iso = datetime.datetime.now().isoformat()
    already_correct = 0
    transcoded = 0
    verified = 0
    failed = []

    for item_id, target_path in rows:
        source = Path(target_path)
        if not source.exists():
            failed.append({"item_id": item_id, "reason": f"Datei fehlt: {source}"})
            continue

        info = _ffprobe_info(source)
        if info["codec_name"] is None:
            failed.append({"item_id": item_id, "reason": f"ffprobe konnte Datei nicht lesen: {source}"})
            continue

        if _is_already_target_format(source, info):
            cur.execute(
                "UPDATE media_items SET transcoded_path = ?, transcoded_at = ?, transcode_verified = 1 WHERE id = ?",
                (str(source), now_iso, item_id),
            )
            already_correct += 1
            continue

        final_path = source.with_suffix(".mp4")
        temp_path = source.with_name(source.stem + ".transcoding.mp4")

        cmd = [
            "ffmpeg", "-y", "-i", str(source),
            "-c:v", resolved_encoder, *quality_args,
            "-c:a", "aac", "-b:a", "192k",
            str(temp_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0 or not temp_path.exists():
            failed.append({"item_id": item_id, "reason": f"ffmpeg fehlgeschlagen: {result.stderr[-300:]}"})
            if temp_path.exists():
                temp_path.unlink()
            continue

        transcoded_info = _ffprobe_info(temp_path)
        if not _durations_match(info["duration"], transcoded_info["duration"]):
            failed.append(
                {
                    "item_id": item_id,
                    "reason": f"Dauer-Mismatch nach Transcoding: {info['duration']} vs {transcoded_info['duration']}",
                }
            )
            temp_path.unlink()
            continue

        if final_path.exists() and final_path != source:
            temp_path.unlink()
            failed.append({"item_id": item_id, "reason": f"Zieldatei existiert bereits: {final_path}"})
            continue

        temp_path.replace(final_path)

        cur.execute(
            "UPDATE media_items SET transcoded_path = ?, transcoded_at = ?, transcode_verified = 1 WHERE id = ?",
            (str(final_path), now_iso, item_id),
        )
        transcoded += 1
        verified += 1

    conn.commit()
    conn.close()

    return {
        "profile_id": profile_id,
        "encoder": resolved_encoder,
        "candidates": len(rows),
        "already_correct": already_correct,
        "transcoded": transcoded,
        "verified": verified,
        "failed": failed,
    }


def delete_pretranscode_sources(profile_id: str, db_path: Path | None = None) -> dict:
    """Löscht die alte (Pre-Transcode) target_path-Datei nur, wenn transcode_verified=1 UND
    transcoded_path existiert UND sich von target_path unterscheidet (bei bereits-korrektem
    Format gibt es nichts zu löschen - dort ist target_path == transcoded_path)."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, target_path, transcoded_path FROM media_items
        WHERE profile_id = ? AND transcode_verified = 1 AND transcoded_path IS NOT NULL
        """,
        (profile_id,),
    )
    rows = cur.fetchall()
    conn.close()

    deleted = 0
    skipped_same_file = 0
    skipped_missing_transcoded = 0
    missing_source = 0

    for _item_id, target_path, transcoded_path in rows:
        old_path = Path(target_path)
        new_path = Path(transcoded_path)

        if old_path == new_path:
            skipped_same_file += 1
            continue
        if not new_path.exists():
            skipped_missing_transcoded += 1
            continue
        if old_path.exists():
            old_path.unlink()
            deleted += 1
        else:
            missing_source += 1

    return {
        "deleted": deleted,
        "skipped_same_file": skipped_same_file,
        "skipped_missing_transcoded": skipped_missing_transcoded,
        "missing_source": missing_source,
    }
