import easycore
from easycore import seed_default_ai_personas
from models import (
    Artist,
    AuthorProfile,
    Comment,
    Playlist,
    PlaylistComment,
    PlaylistVideo,
    Track,
    TrackArtist,
    TrackComment,
    Video,
    db,
)


def create_video(**overrides):
    data = {
        "original_filepath": "clip.mp4",
        "stored_filepath": "clip.mp4",
        "nickname": "Clip",
        "tags": "pop, live",
        "view_count": 0,
        "likes": 0,
    }
    data.update(overrides)
    video = Video(**data)
    db.session.add(video)
    db.session.commit()
    return video


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


def test_increment_video_view_handles_null_count(client):
    video = create_video(view_count=None)

    response = client.post(f"/increment_view/{video.id}")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "new_view_count": 1}
    assert db.session.get(Video, video.id).view_count == 1


def test_like_video_handles_null_count(client):
    video = create_video(likes=None)

    response = client.post(f"/like/{video.id}")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "new_like_count": 1}
    assert db.session.get(Video, video.id).likes == 1


def test_add_video_comment_creates_comment_and_author_artist(client):
    video = create_video()

    response = client.post(
        f"/add_comment/{video.id}",
        data={"author": "Ren Kline", "content": "The edit really works."},
    )

    assert response.status_code == 200
    payload = response.get_json()
    artist = Artist.query.filter_by(name="Ren Kline").one()

    assert payload["success"] is True
    assert payload["comment"]["author_slug"] == "ren-kline"
    assert payload["comment"]["author_artist_id"] == artist.id
    assert Comment.query.filter_by(video_id=video.id).count() == 1


def test_add_video_comment_requires_author_and_content(client):
    video = create_video()

    response = client.post(
        f"/add_comment/{video.id}",
        data={"author": "", "content": ""},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Name and comment are required"}


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


def test_update_track_rejects_invalid_preview_range_without_changes(client):
    track = Track(
        original_filepath="song.mp3",
        stored_filepath="song.mp3",
        nickname="Original",
        description="Existing description",
        tags="old",
    )
    db.session.add(track)
    db.session.commit()

    response = client.post(
        f"/update_track/{track.id}",
        data={
            "nickname": "Updated",
            "description": "Changed",
            "tags": "new",
            "preview_start": "30",
            "preview_end": "10",
            "track_date": "2026-07-03",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Preview end must be after preview start."}
    refreshed = db.session.get(Track, track.id)
    assert refreshed.nickname == "Original"
    assert refreshed.description == "Existing description"
    assert refreshed.tags == "old"


def test_create_playlist_with_video_and_get_playlist(client):
    video = create_video(nickname="Opening Clip", thumbnail_path="thumbnails/opening.jpg")

    response = client.post(
        "/create_playlist",
        data={"name": "Favorites", "description": "Top picks", "video_id": str(video.id)},
    )

    assert response.status_code == 200
    playlist_id = response.get_json()["playlist_id"]
    link = PlaylistVideo.query.filter_by(playlist_id=playlist_id, video_id=video.id).one()
    assert link.position == 1

    playlist_response = client.get(f"/get_playlist/{playlist_id}")
    payload = playlist_response.get_json()["playlist"]
    assert payload["name"] == "Favorites"
    assert payload["videos"][0]["title"] == "Opening Clip"
    assert payload["videos"][0]["position"] == 1


def test_remove_from_playlist_reorders_remaining_videos(client):
    playlist = Playlist(name="Queue")
    videos = [create_video(nickname=f"Clip {idx}") for idx in range(1, 4)]
    db.session.add(playlist)
    db.session.flush()
    for position, video in enumerate(videos, 1):
        db.session.add(
            PlaylistVideo(
                playlist_id=playlist.id,
                video_id=video.id,
                position=position,
            )
        )
    db.session.commit()

    response = client.post(f"/remove_from_playlist/{playlist.id}/{videos[1].id}")

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    remaining = PlaylistVideo.query.filter_by(playlist_id=playlist.id).order_by(PlaylistVideo.position).all()
    assert [(item.video_id, item.position) for item in remaining] == [
        (videos[0].id, 1),
        (videos[2].id, 2),
    ]


def test_delete_playlist_removes_comments_and_video_links(client):
    playlist = Playlist(name="Temporary")
    video = create_video()
    db.session.add(playlist)
    db.session.flush()
    db.session.add(PlaylistVideo(playlist_id=playlist.id, video_id=video.id, position=1))
    db.session.add(PlaylistComment(playlist_id=playlist.id, author="Maya", content="Nice set"))
    db.session.commit()

    response = client.post(f"/delete_playlist/{playlist.id}")

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert db.session.get(Playlist, playlist.id) is None
    assert PlaylistVideo.query.filter_by(playlist_id=playlist.id).count() == 0
    assert PlaylistComment.query.filter_by(playlist_id=playlist.id).count() == 0
    assert db.session.get(Video, video.id) is not None


def test_delete_video_removes_file_and_database_row(client, app):
    video_path = app.config["UPLOAD_FOLDER"] + "/delete-me.mp4"
    with open(video_path, "wb") as file:
        file.write(b"video")
    video = create_video(stored_filepath=video_path)

    response = client.post(f"/delete/{video.id}")

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert db.session.get(Video, video.id) is None
    assert not easycore.os.path.exists(video_path)


def test_get_tag_suggestions_returns_matching_first_tags(client):
    create_video(tags="dream pop, live")
    create_video(tags="ambient, dream pop")
    create_video(tags="pop rock")

    response = client.get("/get_tag_suggestions?q=pop")

    assert response.status_code == 200
    assert response.get_json() == ["pop rock", "dream pop"]


def test_seed_default_ai_personas_is_idempotent(app):
    seed_default_ai_personas()
    seed_default_ai_personas()

    assert AuthorProfile.query.filter_by(is_ai_persona=True).count() == 8
    assert Artist.query.filter_by(name="Maya Vale").count() == 1
