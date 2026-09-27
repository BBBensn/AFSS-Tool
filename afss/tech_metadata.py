import datetime
import json
import subprocess
from pathlib import Path

from afss.db import get_connection

# Commits alle N Dateien statt nur einmal am Ende - bei einem langen, unbeaufsichtigten Lauf
# (z.B. über Nacht, tausende Videos) darf ein Abbruch/Absturz nicht den gesamten bisherigen
# Fortschritt kosten. Ein erneuter Lauf ohne force=True überspringt automatisch alles, was schon
# eine media_technical_info-Zeile hat - macht den Lauf von selbst fortsetzbar.
_COMMIT_EVERY = 50


def _frame_rate(stream: dict) -> float | None:
    raw = stream.get("r_frame_rate")
    if not raw or "/" not in raw:
        return None
    num_str, den_str = raw.split("/", 1)
    try:
        num, den = float(num_str), float(den_str)
    except ValueError:
        return None
    return round(num / den, 3) if den else None


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def probe_technical_info(path: Path) -> dict | None:
    """Ein ffprobe-Aufruf pro Datei liefert Video- UND Audio-Stream plus Format-Infos zusammen -
    liest nur Header/Metadaten (kein Decodieren), ist daher auch für tausende Dateien schnell genug
    für einen Nacht-Lauf. None, wenn ffprobe die Datei nicht lesen konnte (z.B. beschädigt) oder kein
    Video-Stream gefunden wurde."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        return None

    return {
        "width": _to_int(video.get("width")),
        "height": _to_int(video.get("height")),
        "video_codec": video.get("codec_name"),
        "video_bitrate": _to_int(video.get("bit_rate")) or _to_int(fmt.get("bit_rate")),
        "frame_rate": _frame_rate(video),
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_bitrate": _to_int(audio.get("bit_rate")) if audio else None,
        "audio_channels": _to_int(audio.get("channels")) if audio else None,
        "audio_sample_rate": _to_int(audio.get("sample_rate")) if audio else None,
        "duration_seconds": float(fmt["duration"]) if fmt.get("duration") else None,
        "container_format": fmt.get("format_name"),
        "overall_bitrate": _to_int(fmt.get("bit_rate")),
    }


def collect_technical_metadata(profile_id: str, db_path: Path | None = None, force: bool = False) -> dict:
    """Sammelt technische Metadaten (Auflösung/Codec/Bitrate/Framerate/...) für alle Videos eines
    Profils per ffprobe - läuft direkt gegen die aktuelle Quelldatei (media_items.path), unabhängig
    von apply()/transcode(). Bewusst VOR transcode() gedacht: danach ist alles auf ein einheitliches
    Format vereinheitlicht, genau die Unterschiede (Original-Auflösung/-Bitrate/-Codec), die man für
    einen späteren Duplikat-/Qualitätsvergleich braucht, wären dann verschwunden.

    Ohne force=True werden bereits geprobte Dateien übersprungen (Upsert-Tabelle, ein Fund pro
    media_item_id) - macht einen langen, unbeaufsichtigten Lauf sicher fortsetzbar."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    if force:
        cur.execute(
            "SELECT id, path FROM media_items WHERE profile_id = ? AND media_type = 'video'",
            (profile_id,),
        )
    else:
        cur.execute(
            """
            SELECT m.id, m.path FROM media_items m
            LEFT JOIN media_technical_info t ON t.media_item_id = m.id
            WHERE m.profile_id = ? AND m.media_type = 'video' AND t.media_item_id IS NULL
            """,
            (profile_id,),
        )
    rows = cur.fetchall()

    now_iso = datetime.datetime.now().isoformat()
    probed = 0
    failed = []
    since_commit = 0

    for item_id, path_str in rows:
        source = Path(path_str)
        if not source.exists():
            failed.append({"item_id": item_id, "reason": f"Quelle fehlt: {source}"})
            continue

        info = probe_technical_info(source)
        if info is None:
            failed.append({"item_id": item_id, "reason": f"ffprobe konnte Datei nicht lesen: {source}"})
            continue

        cur.execute(
            """
            INSERT INTO media_technical_info(
                media_item_id, width, height, video_codec, video_bitrate, frame_rate,
                audio_codec, audio_bitrate, audio_channels, audio_sample_rate,
                duration_seconds, container_format, overall_bitrate, probed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(media_item_id) DO UPDATE SET
                width=excluded.width, height=excluded.height, video_codec=excluded.video_codec,
                video_bitrate=excluded.video_bitrate, frame_rate=excluded.frame_rate,
                audio_codec=excluded.audio_codec, audio_bitrate=excluded.audio_bitrate,
                audio_channels=excluded.audio_channels, audio_sample_rate=excluded.audio_sample_rate,
                duration_seconds=excluded.duration_seconds, container_format=excluded.container_format,
                overall_bitrate=excluded.overall_bitrate, probed_at=excluded.probed_at
            """,
            (
                item_id, info["width"], info["height"], info["video_codec"], info["video_bitrate"],
                info["frame_rate"], info["audio_codec"], info["audio_bitrate"], info["audio_channels"],
                info["audio_sample_rate"], info["duration_seconds"], info["container_format"],
                info["overall_bitrate"], now_iso,
            ),
        )
        probed += 1
        since_commit += 1
        if since_commit >= _COMMIT_EVERY:
            conn.commit()
            since_commit = 0

    conn.commit()
    conn.close()

    return {
        "profile_id": profile_id,
        "candidates": len(rows),
        "probed": probed,
        "failed": failed,
    }
