"""
Core download engine using yt-dlp for YouTube and TikTok.
Supports single and bulk downloads with progress tracking.
"""

import os
import re
import shutil
import uuid
import threading
import time
import platform
from pathlib import Path

import yt_dlp


def _find_ffmpeg() -> str | None:
    """Find ffmpeg executable path (works on both Windows and Linux)."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return os.path.dirname(ffmpeg_path)
    # Common Windows install locations (only checked on Windows)
    if platform.system() == "Windows":
        for candidate in [
            r"C:\ffmpeg\bin",
            r"C:\Program Files\ffmpeg\bin",
            r"C:\ProgramData\chocolatey\bin",
        ]:
            if os.path.isfile(os.path.join(candidate, "ffmpeg.exe")):
                return candidate
    return None


FFMPEG_DIR = _find_ffmpeg()

# Download directory — use /tmp on Linux (Render), local folder on Windows
if platform.system() == "Windows":
    DOWNLOAD_DIR = Path(__file__).parent / "downloads"
else:
    DOWNLOAD_DIR = Path("/tmp/vidgrab_downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Max age for downloaded files (1 hour) — auto-cleanup on Render
MAX_FILE_AGE_SECONDS = 3600

# Track active downloads: {download_id: {status, progress, filename, ...}}
downloads = {}
downloads_lock = threading.Lock()


def detect_platform(url: str) -> str:
    """Detect whether URL is YouTube or TikTok."""
    url_lower = url.lower().strip()
    if any(domain in url_lower for domain in [
        "youtube.com", "youtu.be", "youtube.com/shorts", "m.youtube.com"
    ]):
        return "youtube"
    elif any(domain in url_lower for domain in [
        "tiktok.com", "vm.tiktok.com", "vt.tiktok.com"
    ]):
        return "tiktok"
    return "unknown"


def get_video_info(url: str) -> dict:
    """Fetch video metadata without downloading."""
    plat = detect_platform(url)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "no_color": True,
        "cookiesfrombrowser": ("chrome",),
    }

    # Use cookies file if available (for YouTube bot verification bypass)
    cookies_file = os.path.join(os.path.dirname(__file__), "cookies.txt")
    if os.path.isfile(cookies_file):
        ydl_opts["cookiefile"] = cookies_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                return {"error": "Could not fetch video info"}

            # Handle playlists
            if info.get("_type") == "playlist":
                entries = []
                for entry in (info.get("entries") or []):
                    if entry:
                        entries.append({
                            "id": entry.get("id", ""),
                            "title": entry.get("title", "Unknown"),
                            "thumbnail": entry.get("thumbnail", ""),
                            "duration": entry.get("duration", 0),
                            "url": entry.get("webpage_url", entry.get("url", "")),
                            "platform": plat,
                        })
                return {
                    "type": "playlist",
                    "title": info.get("title", "Playlist"),
                    "platform": plat,
                    "count": len(entries),
                    "entries": entries,

                }

            # Get available qualities
            formats = info.get("formats", [])
            qualities = set()
            for f in formats:
                height = f.get("height")
                if height and height >= 360:
                    qualities.add(height)

            quality_list = sorted(qualities, reverse=True) if qualities else [1080, 720, 480, 360]

            return {
                "type": "video",
                "id": info.get("id", ""),
                "title": info.get("title", "Unknown"),
                "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration", 0),
                "url": url,
                "platform": plat,
                "qualities": quality_list,
                "uploader": info.get("uploader", "Unknown"),
            }

    except Exception as e:
        return {"error": str(e)}


def _build_ydl_opts(download_id: str, quality: int, plat: str) -> dict:
    """Build yt-dlp options based on platform and quality."""

    def progress_hook(d):
        with downloads_lock:
            if download_id not in downloads:
                return
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed", 0)
                eta = d.get("eta", 0)
                if total > 0:
                    percent = (downloaded / total) * 100
                else:
                    percent = 0
                downloads[download_id].update({
                    "status": "downloading",
                    "progress": round(percent, 1),
                    "downloaded": downloaded,
                    "total": total,
                    "speed": speed or 0,
                    "eta": eta or 0,
                })
            elif d["status"] == "finished":
                downloads[download_id].update({
                    "status": "processing",
                    "progress": 100,
                    "filename": d.get("filename", ""),
                })

    # Common options for all platforms
    ydl_opts = {
        "outtmpl": str(DOWNLOAD_DIR / "%(title).80s_%(id)s.%(ext)s"),
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "merge_output_format": "mp4",
    }

    # Add ffmpeg path if found
    if FFMPEG_DIR:
        ydl_opts["ffmpeg_location"] = FFMPEG_DIR

    # Use cookies file if available (for YouTube bot verification bypass)
    cookies_file = os.path.join(os.path.dirname(__file__), "cookies.txt")
    if os.path.isfile(cookies_file):
        ydl_opts["cookiefile"] = cookies_file

    # Format selection based on quality
    if plat == "tiktok":
        # TikTok: download best quality without watermark
        ydl_opts["format"] = "best"
        ydl_opts["extractor_args"] = {
            "tiktok": {"api_hostname": ["api22-normal-c-useast2a.tiktokv.com"]}
        }
    else:
        # YouTube: select best video+audio up to requested quality, with fallbacks
        ydl_opts["format"] = (
            f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]"
            f"/bestvideo[height<={quality}]+bestaudio"
            f"/best[height<={quality}]"
            f"/best"
        )
        # Postprocessors: merge into mp4 then convert if needed
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegVideoRemuxer",
                "preferedformat": "mp4",
            },
        ]

    return ydl_opts


def _cleanup_old_downloads():
    """Remove downloaded files older than MAX_FILE_AGE_SECONDS."""
    try:
        now = time.time()
        for f in DOWNLOAD_DIR.iterdir():
            if f.is_file() and (now - f.stat().st_mtime) > MAX_FILE_AGE_SECONDS:
                f.unlink()
    except Exception:
        pass


def start_download(url: str, quality: int = 1080) -> str:
    """Start a download in a background thread. Returns download_id."""
    # Clean up old files to prevent disk from filling up
    _cleanup_old_downloads()

    download_id = str(uuid.uuid4())[:8]
    plat = detect_platform(url)

    with downloads_lock:
        downloads[download_id] = {
            "id": download_id,
            "url": url,
            "platform": plat,
            "quality": quality,
            "status": "starting",
            "progress": 0,
            "title": "",
            "filename": "",
            "error": "",
            "downloaded": 0,
            "total": 0,
            "speed": 0,
            "eta": 0,
            "created_at": time.time(),
        }

    def _download():
        try:
            ydl_opts = _build_ydl_opts(download_id, quality, plat)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    filename = ydl.prepare_filename(info)
                    # Check for merged mp4
                    mp4_file = Path(filename).with_suffix(".mp4")
                    if mp4_file.exists():
                        filename = str(mp4_file)

                    with downloads_lock:
                        downloads[download_id].update({
                            "status": "completed",
                            "progress": 100,
                            "title": info.get("title", "Unknown"),
                            "filename": os.path.basename(filename),
                        })
                else:
                    with downloads_lock:
                        downloads[download_id].update({
                            "status": "error",
                            "error": "Failed to download video",
                        })

        except Exception as e:
            with downloads_lock:
                downloads[download_id].update({
                    "status": "error",
                    "error": str(e),
                })

    thread = threading.Thread(target=_download, daemon=True)
    thread.start()

    return download_id


def get_download_status(download_id: str) -> dict:
    """Get the current status of a download."""
    with downloads_lock:
        return downloads.get(download_id, {"error": "Download not found"})


def get_all_downloads() -> list:
    """Get all download statuses."""
    with downloads_lock:
        return sorted(
            downloads.values(),
            key=lambda x: x.get("created_at", 0),
            reverse=True,
        )


def format_bytes(size: float) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
