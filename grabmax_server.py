"""
GRABMAX Backend Server v4.3 - Railway Fix
==========================================
Forces AAC audio in all MP4 downloads.
Fixed PORT binding for Railway deployment.
"""

import os, io, tempfile, traceback
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

try:
    import yt_dlp
except ImportError:
    raise SystemExit("Run: pip install yt-dlp flask flask-cors")

app = Flask(__name__)
CORS(app)

BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "cookiefile": os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt"),  # ← ADD THIS LINE
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    },
}
# ── health check so Railway knows app is alive ────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "GRABMAX is running", "version": "4.3"}), 200


# ── /info ─────────────────────────────────────────────────────────────────────
@app.route("/info", methods=["POST"])
def get_info():
    data = request.get_json(force=True)
    url  = (data or {}).get("url", "").strip()
    if not url:           return jsonify({"error": "No URL provided"}), 400
    if not _allowed(url): return jsonify({"error": "Only YouTube and Instagram URLs are supported"}), 400

    try:
        with yt_dlp.YoutubeDL({**BASE_OPTS, "skip_download": True}) as ydl:
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
    data      = request.get_json(force=True)
    url       = (data or {}).get("url", "").strip()
    format_id = (data or {}).get("format_id", "bestvideo+bestaudio/best")
    ext       = (data or {}).get("ext", "mp4")

    if not url:           return jsonify({"error": "No URL provided"}), 400
    if not _allowed(url): return jsonify({"error": "Only YouTube and Instagram URLs supported"}), 400

    with tempfile.TemporaryDirectory() as tmp:
        out_tmpl = os.path.join(tmp, "%(title).80s.%(ext)s")

        if ext in ("mp3", "m4a"):
            ydl_opts = {
                **BASE_OPTS,
                "format":  "bestaudio/best",
                "outtmpl": out_tmpl,
                "postprocessors": [{
                    "key":              "FFmpegExtractAudio",
                    "preferredcodec":   ext,
                    "preferredquality": "320" if ext == "mp3" else "0",
                }],
            }
        else:
            ydl_opts = {
                **BASE_OPTS,
                "format":              format_id,
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
    print(f"  GRABMAX Backend v4.3  — port {port}")
    print(f"  Audio: Opus → AAC fix applied")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
