# easycore

easycore is a local Flask media library for organizing videos, tracks, artists, playlists, tags, comments, likes, and generated thumbnails. It stores metadata in SQLite and keeps uploaded media files in local folders.

## Features

- Upload, stream, tag, describe, and delete videos.
- Upload and manage audio tracks with artists, artwork, previews, likes, comments, and view counts.
- Create playlists and add or remove videos.
- Browse by tags, artists, tracks, playlists, newest, oldest, most viewed, or most liked.
- Generate video thumbnails and convert WebM uploads to MP4 with FFmpeg.
- Extract MP3 audio and trim videos.
- Use optional OpenRouter-powered comment generation for tracks and artists.

## Project Structure

```text
easycore.py              Main Flask application and route definitions
models.py                SQLAlchemy database models
routes/                  Flask blueprints for videos, playlists, comments, and filters
templates/               Jinja templates
static/css/              Application styles
static/js/               Frontend JavaScript
requirements.txt         Python dependencies
AI_COMMENT_SETUP.md      Optional AI comment setup details
update_thumbnails.py     Helper script for regenerating thumbnails
releasenotes.md          Version notes
```

Runtime files are created locally and ignored by Git, including `instance/`, `uploads/`, `uploads_audio/`, `stealth_uploads/`, `stealth_audio_uploads/`, generated thumbnails, covers, avatars, and SQLite database files.

## Requirements

- Python 3.10 or newer
- FFmpeg installed and available on your `PATH`
- Optional: an OpenRouter API key for AI comment generation

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Confirm FFmpeg is available:

```powershell
ffmpeg -version
```

## Running the App

Start the Flask server:

```powershell
python easycore.py
```

The app initializes required folders, creates missing SQLite tables, and starts at:

```text
http://127.0.0.1:5015
```

## Optional AI Comments

AI comment generation uses the `OPENROUTER_API_KEY` environment variable and defaults to `deepseek/deepseek-v4-pro`.

For the current PowerShell session:

```powershell
$env:OPENROUTER_API_KEY = "your_api_key_here"
python easycore.py
```

Optional overrides:

```powershell
$env:OPENROUTER_MODEL = "deepseek/deepseek-v4-pro"
$env:OPENROUTER_SITE_NAME = "easycore"
$env:OPENROUTER_SITE_URL = "http://127.0.0.1:5015"
```

See [AI_COMMENT_SETUP.md](AI_COMMENT_SETUP.md) for feature behavior, prompt styles, troubleshooting, and cost notes.

Track and artist pages include AI listener personas. Use AI assist to draft a comment from a selected or random listener, or post an AI listener reaction directly into the existing comment thread.

## Useful Routes

- `/` - video library
- `/video/add` - add a video
- `/bulk_upload` - bulk upload videos
- `/tracks` - track library
- `/add_track` - add an audio track
- `/artists` - artist library
- `/add_artist` - add an artist
- `/playlist/<playlist_id>` - playlist detail
- `/tag/<tag>` - tag detail
- `/extract_mp3` - extract MP3 from video

## Maintenance

Regenerate thumbnails for videos that do not already have one:

```powershell
python update_thumbnails.py
```

The app stores media files on disk and metadata in SQLite, so keep backups of both the upload folders and the database file if the library matters.
