from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filepath = db.Column(db.String(255), nullable=False)
    stored_filepath = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(100))
    description = db.Column(db.Text)
    tags = db.Column(db.String(255))
    thumbnail_path = db.Column(db.String(255))
    view_count = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    playlists = db.relationship('Playlist', secondary='playlist_video',
                               backref=db.backref('videos', lazy='dynamic'))
    artists = db.relationship('Artist', secondary='video_artist', back_populates='videos')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)
    author_artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=True)

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PlaylistVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)

class PlaylistComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)
    author_artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=True)

class TagDescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TagComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)
    author_artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=True) 


class Track(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filepath = db.Column(db.String(255), nullable=False)
    stored_filepath = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(100))
    album = db.Column(db.String(150))
    track_date = db.Column(db.Date, default=lambda: date.today())
    description = db.Column(db.Text)
    tags = db.Column(db.String(255))
    background_image_path = db.Column(db.String(255))
    preview_start = db.Column(db.Float, nullable=True)
    preview_end = db.Column(db.Float, nullable=True)
    preview_fade_in = db.Column(db.Boolean, default=False)
    preview_fade_out = db.Column(db.Boolean, default=False)
    preview_fade_in_seconds = db.Column(db.Float, default=2.0)
    preview_fade_out_seconds = db.Column(db.Float, default=2.0)
    preview_default = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    artists = db.relationship('Artist', secondary='track_artist', back_populates='tracks')


class TrackComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)
    author_artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=True)


class ArtistComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)
    author_artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=True)


class Artist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    bio = db.Column(db.Text)
    avatar_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tracks = db.relationship('Track', secondary='track_artist', back_populates='artists')
    videos = db.relationship('Video', secondary='video_artist', back_populates='artists')


class TrackArtist(db.Model):
    __tablename__ = 'track_artist'
    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'), nullable=False)
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=False)


class VideoArtist(db.Model):
    __tablename__ = 'video_artist'
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=False)


class AuthorProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    display_name = db.Column(db.String(150), nullable=True)
    avatar_path = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    is_ai_persona = db.Column(db.Boolean, default=False)
    personality = db.Column(db.Text, nullable=True)
    taste_profile = db.Column(db.Text, nullable=True)
    comment_style = db.Column(db.String(100), nullable=True)
    activity_level = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
