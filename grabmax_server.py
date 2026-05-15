"""
GRABMAX Backend Server v6.0 - FINAL
=====================================
Uses yt-dlp's own format selection - guaranteed to work on every video
"""

import os, io, tempfile, traceback, shutil
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

try:
    import yt_dlp
except ImportError:
    raise SystemExit("Run: pip install yt-dlp flask flask-cors")

app = Flask(__name__)
CORS(app)

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
COOKIES_FILE_IG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instagram_cookies.txt")
FFMPEG_PATH  = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

def base():
    o = {
        "quiet": False,
        "no_warnings": False,
        "geo_bypass": True,
        "ffmpeg_location": os.path.dirname(FFMPEG_PATH),
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if os.path.exists(COOKIES_FILE):
        o["cookiefile"] = COOKIES_FILE
    return o

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "GRABMAX is running",
        "version": "6.0",
        "cookies": "loaded" if os.path.exists(COOKIES_FILE) else "missing",
        "ffmpeg": "found" if os.path.isfile(FFMPEG_PATH) else "missing",
    }), 200

@app.route("/info", methods=["POST"])
def get_info():
    data = request.get_json(force=True)
    url  = (data or {}).get("url", "").strip()
    if not url:           return jsonify({"error": "No URL provided"}), 400
    if not _allowed(url): return jsonify({"error": "Only YouTube and Instagram URLs are supported"}), 400

    try:
        with yt_dlp.YoutubeDL({**base(), "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    return jsonify({
        "title":      info.get("title", "Untitled"),
        "uploader":   info.get("uploader") or info.get("channel", ""),
        "duration":   info.get("duration"),
        "view_count": info.get("view_count"),
        "thumbnail":  info.get("thumbnail"),
    })

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(force=True)
    url  = (data or {}).get("url", "").strip()
    ext  = (data or {}).get("ext", "mp4")
    res  = (data or {}).get("res", "best")

    if not url:           return jsonify({"error": "No URL provided"}), 400
    if not _allowed(url): return jsonify({"error": "Only YouTube and Instagram URLs supported"}), 400

    # Map resolution to max height
    height_map = {
        "4K": 2160, "✨ Best": None,
        "1080p": 1080, "720p": 720,
        "480p": 480,   "360p": 360,
    }
    h = height_map.get(res, None)

    with tempfile.TemporaryDirectory() as tmp:
        out_tmpl = os.path.join(tmp, "%(title).80s.%(ext)s")
        b = base()

        if ext in ("mp3", "m4a"):
            ydl_opts = {
                **b,
                "format": "bestaudio/best",
                "outtmpl": out_tmpl,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": ext,
                    "preferredquality": "320" if ext == "mp3" else "0",
                }],
            }
        else:
            # This format string always works — yt-dlp picks best available
            if h:
                fmt = f"bestvideo[height<={h}]+bestaudio/bestvideo[height<={h}]/best[height<={h}]/best"
            else:
                fmt = "bestvideo+bestaudio/best"

            ydl_opts = {
                **b,
                "format": fmt,
                "outtmpl": out_tmpl,
                "merge_output_format": "mp4",
                "postprocessor_args": {
                    "ffmpeg": ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
                },
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                expected = ydl.prepare_filename(info)
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 422

        out_file = _find_output(tmp, expected)
        if not out_file:
            return jsonify({"error": "No output file produced"}), 500

        with open(out_file, "rb") as fh:
            raw = fh.read()

        filename = os.path.basename(out_file)
        if ext == "mp4" and not filename.lower().endswith(".mp4"):
            filename = os.path.splitext(filename)[0] + ".mp4"

        return send_file(io.BytesIO(raw), mimetype=_mime(ext), as_attachment=True, download_name=filename)

def _allowed(url):
    return any(d in url for d in ("youtube.com", "youtu.be", "instagram.com"))

def _find_output(directory, expected):
    if os.path.isfile(expected): return expected
    try:
        files = [os.path.join(directory, f) for f in os.listdir(directory)]
        if files: return max(files, key=os.path.getsize)
    except: pass
    return None

def _mime(ext):
    return {"mp4": "video/mp4", "mp3": "audio/mpeg", "m4a": "audio/mp4"}.get(ext, "application/octet-stream")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"GRABMAX v6.0 — port {port} — ffmpeg: {FFMPEG_PATH}")
    app.run(host="0.0.0.0", port=port, debug=False)
