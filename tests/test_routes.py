from easycore import seed_default_ai_personas
from models import Artist, AuthorProfile, Track, TrackComment, db


def test_index_renders_empty_library(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data


def test_like_track_increments_count(client):
    track = Track(
        original_filepath="song.mp3",
        stored_filepath="song.mp3",
        nickname="Song",
        likes=None,
    )
    db.session.add(track)
    db.session.commit()

    response = client.post(f"/like_track/{track.id}")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "new_like_count": 1}
    assert db.session.get(Track, track.id).likes == 1


def test_add_track_comment_creates_comment_and_author_artist(client):
    track = Track(
        original_filepath="song.mp3",
        stored_filepath="song.mp3",
        nickname="Song",
    )
    db.session.add(track)
    db.session.commit()

    response = client.post(
        f"/add_track_comment/{track.id}",
        data={"author": "Maya Vale", "content": "That chorus lands."},
    )

    assert response.status_code == 200
    payload = response.get_json()
    artist = Artist.query.filter_by(name="Maya Vale").one()

    assert payload["success"] is True
    assert payload["comment"]["author_slug"] == "maya-vale"
    assert payload["comment"]["author_artist_id"] == artist.id
    assert TrackComment.query.filter_by(track_id=track.id).count() == 1


def test_add_track_comment_requires_author_and_content(client):
    track = Track(original_filepath="song.mp3", stored_filepath="song.mp3")
    db.session.add(track)
    db.session.commit()

    response = client.post(
        f"/add_track_comment/{track.id}",
        data={"author": "", "content": ""},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Name and comment are required"}


def test_seed_default_ai_personas_is_idempotent(app):
    seed_default_ai_personas()
    seed_default_ai_personas()

    assert AuthorProfile.query.filter_by(is_ai_persona=True).count() == 8
    assert Artist.query.filter_by(name="Maya Vale").count() == 1
