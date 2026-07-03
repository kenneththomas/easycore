import easycore
from easycore import seed_default_ai_personas
from models import Artist, AuthorProfile, Track, TrackArtist, TrackComment, db


def test_index_renders_empty_library(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data


def test_first_request_initializes_missing_tables(client):
    db.drop_all()
    easycore._track_preview_schema_checked = False
    easycore._author_profile_schema_checked = False
    easycore._database_initialized = False

    response = client.get("/")

    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data


def test_first_request_recovers_when_initialized_flag_is_stale(client):
    db.drop_all()
    easycore._database_initialized = True

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


def test_update_track_artists_replaces_artist_links(client):
    track = Track(original_filepath="song.mp3", stored_filepath="song.mp3")
    db.session.add(track)
    db.session.commit()

    response = client.post(
        f"/update_track_artists/{track.id}",
        data={"artist_names": "Maya Vale, Ren Kline, Maya Vale"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert [artist["name"] for artist in payload["artists"]] == ["Maya Vale", "Ren Kline"]
    assert Artist.query.filter(Artist.name.in_(["Maya Vale", "Ren Kline"])).count() == 2
    assert TrackArtist.query.filter_by(track_id=track.id).count() == 2

    response = client.post(
        f"/update_track_artists/{track.id}",
        data={"artist_names": "Sasha Mori"},
    )

    assert response.status_code == 200
    assert [artist["name"] for artist in response.get_json()["artists"]] == ["Sasha Mori"]
    assert TrackArtist.query.filter_by(track_id=track.id).count() == 1


def test_seed_default_ai_personas_is_idempotent(app):
    seed_default_ai_personas()
    seed_default_ai_personas()

    assert AuthorProfile.query.filter_by(is_ai_persona=True).count() == 8
    assert Artist.query.filter_by(name="Maya Vale").count() == 1
