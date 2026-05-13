✅ Step 1 — Install Python

Go to https://python.org/downloads and download the latest Python (3.11+)
Run the installer — check "Add Python to PATH" before clicking Install
Verify it worked: open Command Prompt and type:

   python --version
You should see something like Python 3.12.x

✅ Step 2 — Install FFmpeg
FFmpeg is needed to merge video + audio into a single file.

Go to https://www.gyan.dev/ffmpeg/builds/
Download ffmpeg-release-essentials.zip
Extract it — e.g. to C:\ffmpeg
Add it to PATH:

Press Win + S → search "Environment Variables"
Click "Edit the system environment variables"
Click "Environment Variables" → under System Variables, find Path → click Edit
Click New → paste C:\ffmpeg\bin → OK all the way out


Verify: open a new Command Prompt and type:

   ffmpeg -version
Should show FFmpeg version info.

✅ Step 3 — Install Python Packages
Open Command Prompt and run:
pip install yt-dlp flask flask-cors
Wait for it to finish (takes ~30 seconds).

✅ Step 4 — Run the Backend Server

Put both files (downloader.html and grabmax_server.py) in the same folder, e.g. C:\Users\YourName\Desktop\grabmax\
Open Command Prompt in that folder:

Navigate to the folder in File Explorer
Click the address bar, type cmd, press Enter


Run:

   python grabmax_server.py

You should see:

   ====================================================
     GRABMAX Backend Server  —  http://localhost:5000
   ====================================================
Keep this window open — don't close it.

✅ Step 5 — Open the Website

Open the downloader.html file in your browser (double-click it, or drag it into Chrome/Edge/Firefox)
Paste any YouTube or Instagram URL
Click Analyze → and then ↓ Download
