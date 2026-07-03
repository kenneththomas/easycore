import pytest
import os

os.environ.setdefault("EASYCORE_DATABASE_URI", "sqlite:///:memory:")
import easycore
from easycore import app as flask_app
from models import db


@pytest.fixture()
def app(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    flask_app.config.update(
        TESTING=True,
        UPLOAD_FOLDER=str(data_dir / "uploads"),
        STEALTH_UPLOAD_FOLDER=str(data_dir / "stealth_uploads"),
        AUDIO_UPLOAD_FOLDER=str(data_dir / "uploads_audio"),
        STEALTH_AUDIO_UPLOAD_FOLDER=str(data_dir / "stealth_audio_uploads"),
        COVER_FOLDER=str(data_dir / "covers"),
        AVATAR_FOLDER=str(data_dir / "avatars"),
    )

    easycore._track_preview_schema_checked = False
    easycore._author_profile_schema_checked = False
    easycore._database_initialized = False

    with flask_app.app_context():
        easycore.ensure_directories_exist()
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
