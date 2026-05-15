"""
GRABMAX Backend Server v5.0
============================
- Ignores frontend format_id, uses smart fallback always
- FFmpeg auto-detection
- AAC audio fix
- Cookie support
- Railway PORT fix
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
FFMPEG_PATH  = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

def get_base_opts():
    opts = {
        "quiet": False,
        "no_warnings": False,
        "geo_bypass": True,
        "ffmpeg_location": os.path.dirname(FFMPEG_PATH),
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    return opts

def smart_format(res, ext):
    """
    Build a format string with multiple fallbacks.
    NEVER fails — always finds something to download.
    """
    if ext in ("mp3", "m4a"):
        return "bestaudio/best"

    # Map resolution label to height
    h = {
        "4K": 2160, "2160p": 2160,
        "1080p": 1080, "1080": 1080,
        "720p": 720,   "720": 720,
        "480p": 480,   "480": 480,
        "360p": 360,   "360": 360,
    }.get(str(res), None)

    if h:
        return (
            f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]"
            f"/bestvideo[height<={h}]+bestaudio"
            f"/bestvideo[height<={h}]"
            f"/bestvideo+bestaudio"
            f"/best"
        )
    # Best quality with full fallback chain
    return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"


# ── health check ──────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status":      "GRABMAX is running",
        "version":     "5.0",
        "cookies":     "loaded" if os.path.exists(COOKIES_FILE) else "missing",
        "ffmpeg":      "found" if os.path.isfile(FFMPEG_PATH) else "missing",
        "ffmpeg_path": FFMPEG_PATH,
    }), 200


# ── /info ─────────────────────────────────────────────────────────────────────
@app.route("/info", methods=["POST"])
def get_info():
    data = request.get_json(force=True)
    url  = (data or {}).get("url", "").strip()
    if not url:           return jsonify({"error": "No URL provided"}), 400
    if not _allowed(url): return jsonify({"error": "Only YouTube and Instagram URLs are supported"}), 400

    opts = {**get_base_opts(), "skip_download": True}

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    formats = [
        {
            "format_id":   f.get("format_id"),
            "ext":         f.get("ext"),
            "height":      f.get("height"),
            "width":       f.get("width"),
            "fps":         f.get("fps"),
            "vcodec":      f.get("vcodec"),
            "acodec":      f.get("acodec"),
            "abr":         f.get("abr"),
            "filesize":    f.get("filesize") or f.get("filesize_approx"),
            "format_note": f.get("format_note", ""),
        }
        for f in info.get("formats", [])
    ]

    return jsonify({
        "title":       info.get("title", "Untitled"),
        "uploader":    info.get("uploader") or info.get("channel"),
        "duration":    info.get("duration"),
        "view_count":  info.get("view_count"),
        "thumbnail":   info.get("thumbnail"),
        "webpage_url": info.get("webpage_url", url),
        "formats":     formats,
    })


# ── /download ─────────────────────────────────────────────────────────────────
@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(force=True)
    url  = (data or {}).get("url", "").strip()
    ext  = (data or {}).get("ext", "mp4")
    res  = (data or {}).get("res", "best")  # resolution label from frontend

    if not url:           return jsonify({"error": "No URL provided"}), 400
    if not _allowed(url): return jsonify({"error": "Only YouTube and Instagram URLs supported"}), 400

    # Always use smart format — ignore format_id from frontend
    fmt = smart_format(res, ext)
    print(f"[GRABMAX] Downloading: {url} | res={res} ext={ext} | fmt={fmt}")

    with tempfile.TemporaryDirectory() as tmp:
        out_tmpl = os.path.join(tmp, "%(title).80s.%(ext)s")
        base = get_base_opts()

        if ext in ("mp3", "m4a"):
            ydl_opts = {
                **base,
                "format":  fmt,
                "outtmpl": out_tmpl,
                "postprocessors": [{
                    "key":              "FFmpegExtractAudio",
                    "preferredcodec":   ext,
                    "preferredquality": "320" if ext == "mp3" else "0",
                }],
            }
        else:
            ydl_opts = {
                **base,
                "format":              fmt,
                "outtmpl":             out_tmpl,
                "merge_output_format": "mp4",
                "postprocessors": [{
                    "key":            "FFmpegVideoRemuxer",
                    "preferedformat": "mp4",
                }],
                "postprocessor_args": {
                    "ffmpeg": [
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-movflags", "+faststart",
                    ]
                },
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info     = ydl.extract_info(url, download=True)
                expected = ydl.prepare_filename(info)
        except yt_dlp.utils.DownloadError as e:
            return jsonify({"error": str(e)}), 422
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

        out_file = _find_output(tmp, expected)
        if not out_file:
            return jsonify({"error": "Download produced no output file"}), 500

        with open(out_file, "rb") as fh:
            raw = fh.read()

        filename = os.path.basename(out_file)
        if ext == "mp4" and not filename.lower().endswith(".mp4"):
            filename = os.path.splitext(filename)[0] + ".mp4"

        return send_file(
            io.BytesIO(raw),
            mimetype=_mime(ext),
            as_attachment=True,
            download_name=filename,
        )


# ── helpers ───────────────────────────────────────────────────────────────────
def _allowed(url):
    return any(d in url for d in ("youtube.com", "youtu.be", "instagram.com"))

def _find_output(directory, expected):
    if os.path.isfile(expected):
        return expected
    try:
        files = [os.path.join(directory, f) for f in os.listdir(directory)]
        if files:
            return max(files, key=os.path.getsize)
    except Exception:
        pass
    return None

def _mime(ext):
    return {
        "mp4":  "video/mp4",
        "webm": "video/webm",
        "mkv":  "video/x-matroska",
        "mp3":  "audio/mpeg",
        "m4a":  "audio/mp4",
    }.get(ext, "application/octet-stream")


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"\n{'='*50}")
    print(f"  GRABMAX Backend v5.0  —  port {port}")
    print(f"  FFmpeg: {FFMPEG_PATH}")
    print(f"  Cookies: {'loaded' if os.path.exists(COOKIES_FILE) else 'missing'}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
