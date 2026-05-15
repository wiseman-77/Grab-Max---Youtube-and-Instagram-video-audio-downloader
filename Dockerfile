FROM python:3.12-slim

# Install ffmpeg directly - guaranteed to work
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy all files
COPY . .

# Install Python packages
RUN pip install --no-cache-dir yt-dlp flask flask-cors gunicorn

# Verify ffmpeg installed
RUN ffmpeg -version

# Start server
CMD gunicorn grabmax_server:app --bind 0.0.0.0:$PORT --workers 1 --timeout 300
