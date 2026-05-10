"""
Flask web server for YouTube & TikTok Video Downloader.
Provides REST API endpoints and serves the web UI.
"""

import os
import json
import time
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory, Response

from downloader import (
    get_video_info,
    start_download,
    get_download_status,
    get_all_downloads,
    detect_platform,
    DOWNLOAD_DIR,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max request


@app.route("/")
def index():
    """Serve the main UI page."""
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def video_info():
    """Fetch video info from a URL."""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "URL is required"}), 400

    url = data["url"].strip()
    if not url:
        return jsonify({"error": "URL cannot be empty"}), 400

    info = get_video_info(url)
    return jsonify(info)


@app.route("/api/bulk-info", methods=["POST"])
def bulk_video_info():
    """Fetch info for multiple URLs."""
    data = request.get_json()
    if not data or "urls" not in data:
        return jsonify({"error": "URLs are required"}), 400

    urls = [u.strip() for u in data["urls"] if u.strip()]
    results = []
    for url in urls:
        info = get_video_info(url)
        info["url"] = url
        results.append(info)

    return jsonify({"results": results})


@app.route("/api/download", methods=["POST"])
def download():
    """Start a download."""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "URL is required"}), 400

    url = data["url"].strip()
    quality = data.get("quality", 1080)

    download_id = start_download(url, quality)
    return jsonify({"download_id": download_id, "status": "started"})


@app.route("/api/bulk-download", methods=["POST"])
def bulk_download():
    """Start multiple downloads."""
    data = request.get_json()
    if not data or "urls" not in data:
        return jsonify({"error": "URLs are required"}), 400

    quality = data.get("quality", 1080)
    download_ids = []

    for url in data["urls"]:
        url = url.strip()
        if url:
            did = start_download(url, quality)
            download_ids.append(did)
            time.sleep(0.2)  # Small delay between downloads

    return jsonify({"download_ids": download_ids, "status": "started"})


@app.route("/api/progress/<download_id>")
def progress(download_id):
    """SSE endpoint for download progress."""
    def generate():
        while True:
            status = get_download_status(download_id)
            yield f"data: {json.dumps(status)}\n\n"
            if status.get("status") in ("completed", "error"):
                break
            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/downloads")
def list_downloads():
    """List all downloads."""
    return jsonify({"downloads": get_all_downloads()})


@app.route("/api/file/<filename>")
def serve_file(filename):
    """Serve a downloaded file."""
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("RENDER") is None  # Debug only when NOT on Render
    print("\n" + "=" * 60)
    print("  YouTube & TikTok Video Downloader")
    print("  Downloads folder:", DOWNLOAD_DIR)
    if debug:
        print(f"  Open http://localhost:{port} in your browser")
    else:
        print("  Running in production mode")
    print("=" * 60 + "\n")
    app.run(debug=debug, host="0.0.0.0", port=port)
