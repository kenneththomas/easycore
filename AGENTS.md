# AGENTS.md

Guidance for coding agents working in this repository.

## Project Overview

EasyCore is a local Flask media library. It manages videos, audio tracks, artists, playlists, tags, comments, likes, generated thumbnails, and optional AI-generated comments.

The app is intentionally simple: a Flask server, SQLite database, local upload folders, Jinja templates, and static CSS/JavaScript.

## Important Files

- `easycore.py` - main Flask application, routes, startup initialization, and many helper functions.
- `models.py` - SQLAlchemy models.
- `routes/` - Flask blueprints for video, playlist, comment, and filter behavior.
- `templates/` - Jinja HTML templates.
- `static/css/` - stylesheets.
- `static/js/` - browser-side behavior.
- `requirements.txt` - Python dependencies.
- `README.md` - setup and usage documentation.
- `AI_COMMENT_SETUP.md` - optional OpenRouter comment generation setup.
- `update_thumbnails.py` - helper script for regenerating missing video thumbnails.

## Runtime Behavior

Run the app with:

```powershell
python easycore.py
```

On startup, the app:

- creates required upload/static directories,
- creates missing SQLite tables,
- ensures track preview columns exist,
- starts Flask on `0.0.0.0:5015`.

Local URL:

```text
http://127.0.0.1:5015
```

## Dependencies

Install Python dependencies with:

```powershell
pip install -r requirements.txt
```

FFmpeg must be installed and available on `PATH`. The app uses FFmpeg for video conversion, thumbnail generation, MP3 extraction, and trimming.

Optional AI comment generation requires:

```powershell
$env:OPENROUTER_API_KEY = "your_api_key_here"
```

## Generated And Local Data

Do not commit generated media, local database files, or runtime assets. They are ignored by `.gitignore`.

Important ignored paths include:

- `instance/`
- `uploads/`
- `uploads_audio/`
- `stealth_uploads/`
- `stealth_audio_uploads/`
- `static/thumbnails/`
- `static/avatars/`
- `static/covers/`
- `*.db`
- `.venv/`

Treat these folders as user data. Do not delete, rename, or bulk rewrite them unless the user explicitly asks.

## Development Notes

- Prefer small, direct changes that match the current Flask/Jinja/SQLAlchemy style.
- Keep route behavior backward compatible where possible; templates and JavaScript often call routes by exact URL.
- This project currently has duplicated route/helper logic between `easycore.py` and some files under `routes/`. Check both before changing shared behavior.
- When adding database fields, include startup compatibility logic if existing local SQLite databases need to keep working.
- Use `secure_filename` or existing filename helpers for uploaded files.
- Keep upload paths local and do not expose absolute filesystem paths to templates or API responses unless the existing code already does so.
- Avoid broad refactors unless the user specifically asks for cleanup.

## Verification

There is no formal test suite in the repository at the moment. For changes, prefer the smallest useful verification:

- syntax check changed Python files,
- run the Flask app when route behavior changes,
- manually exercise the affected page or endpoint,
- check browser console/network behavior for frontend changes.

Useful commands:

```powershell
python -m py_compile easycore.py models.py
python update_thumbnails.py
```

Only run `update_thumbnails.py` when thumbnail regeneration is relevant, because it touches generated assets.

## Documentation

Update `README.md` when setup, runtime behavior, dependencies, ports, or major user-facing workflows change.

Update `releasenotes.md` only when the user asks for release notes or the change clearly belongs in the project history.
