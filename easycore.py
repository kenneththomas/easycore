from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, Response, make_response
import os
from sqlalchemy import desc, func
import re
from werkzeug.utils import secure_filename
import ffmpeg
from PIL import Image
import io
from werkzeug.datastructures import FileStorage
from datetime import datetime
import uuid
import random
import string
import unicodedata
import markdown

# Import models
from models import db, Video, Comment, Playlist, PlaylistVideo, PlaylistComment, TagDescription, TagComment, Track, TrackComment, ArtistComment, Artist, TrackArtist, VideoArtist, AuthorProfile

# Import blueprints
from routes import video_bp, playlist_bp, comment_bp, filter_bp

# Import AI comment generator
from ai_comment_generator import get_ai_generator

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///videos.db'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
app.config['STEALTH_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'stealth_uploads')
app.config['AUDIO_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads_audio')
app.config['STEALTH_AUDIO_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'stealth_audio_uploads')
app.config['COVER_FOLDER'] = os.path.join(app.static_folder, 'covers')
app.config['AVATAR_FOLDER'] = os.path.join(app.static_folder, 'avatars')

# Initialize the db with this app
db.init_app(app)

# Register blueprints
app.register_blueprint(video_bp, url_prefix='/video')
app.register_blueprint(playlist_bp, url_prefix='/playlist')
app.register_blueprint(comment_bp, url_prefix='/comment')
app.register_blueprint(filter_bp, url_prefix='/filter')

# Add markdown filter
@app.template_filter('markdown')
def markdown_filter(text):
    if not text:
        return ''
    return markdown.markdown(text, extensions=['nl2br', 'fenced_code'])

def slugify_author(author_name: str) -> str:
    """Create a URL-safe slug from an author name.
    - Lowercase
    - Normalize accents
    - Replace non-alphanumeric with single hyphens
    - Trim hyphens
    """
    if not author_name:
        return ""
    normalized = unicodedata.normalize('NFKD', author_name)
    ascii_only = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = ascii_only.lower()
    slug_chars = []
    prev_dash = False
    for ch in lowered:
        if ch.isalnum():
            slug_chars.append(ch)
            prev_dash = False
        else:
            if not prev_dash:
                slug_chars.append('-')
                prev_dash = True
    slug = ''.join(slug_chars).strip('-')
    return slug

def get_or_create_artist_by_name(artist_name: str) -> Artist:
    """Get or create an artist by name. This is used when someone comments to automatically create their artist page."""
    if not artist_name:
        return None
    
    # Try to find existing artist by name (case insensitive)
    artist = Artist.query.filter(Artist.name.ilike(artist_name)).first()
    
    if not artist:
        # Create new artist
        artist = Artist(name=artist_name)
        db.session.add(artist)
        db.session.flush()  # Get the ID
    
    return artist

# Expose slugify to templates
app.jinja_env.filters['slugify'] = slugify_author

@app.route('/artist/<artist_name>')
def artist_by_name(artist_name: str):
    """Route to handle artist pages by name (for backward compatibility with comment links)."""
    # Try to find artist by name (case insensitive)
    artist = Artist.query.filter(Artist.name.ilike(artist_name)).first()
    
    if not artist:
        # If no artist found, create one
        artist = Artist(name=artist_name)
        db.session.add(artist)
        db.session.commit()
    
    return redirect(url_for('artist_detail', artist_id=artist.id))

@app.route('/artist/<int:artist_id>/avatar', methods=['POST'])
def upload_artist_avatar(artist_id: int):
    artist = Artist.query.get_or_404(artist_id)
    avatar = request.files.get('avatar')
    if not avatar or not avatar.filename:
        return redirect(url_for('artist_detail', artist_id=artist_id))

    try:
        ext = os.path.splitext(avatar.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            return redirect(url_for('artist_detail', artist_id=artist_id))

        filename = secure_filename(f"artist_{artist_id}_{uuid.uuid4().hex}{ext}")
        abs_path = os.path.join(app.config['AVATAR_FOLDER'], filename)
        os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)
        avatar.save(abs_path)
        rel_path = os.path.join('avatars', filename).replace('\\', '/')

        artist.avatar_path = rel_path
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect(url_for('artist_detail', artist_id=artist_id))

def ensure_directories_exist():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['STEALTH_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['AUDIO_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['STEALTH_AUDIO_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['COVER_FOLDER'], exist_ok=True)
    os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)

def convert_webm_to_mp4(input_path):
    """Convert WebM file to MP4 and return the new filepath"""
    output_path = os.path.splitext(input_path)[0] + '.mp4'
    try:
        (
            ffmpeg
            .input(input_path)
            .output(output_path, acodec='aac', vcodec='h264', **{'b:v': '2M'})
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        os.remove(input_path)  # Remove original WebM file
        return output_path
    except ffmpeg.Error as e:
        print(f"Error converting WebM to MP4: {e.stderr.decode()}")
        raise

def generate_unique_filename(original_filename, upload_folder):
    """Generate a unique filename by adding timestamp and random string if needed"""
    name, ext = os.path.splitext(original_filename)
    filename = secure_filename(name + ext)
    filepath = os.path.join(upload_folder, filename)
    
    # If file already exists, add timestamp and random string
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        filename = secure_filename(f"{name}_{timestamp}_{random_string}{ext}")
        filepath = os.path.join(upload_folder, filename)
    
    return filename, filepath

def get_mime_type_for_audio(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.mp3']:  # default and most common
        return 'audio/mpeg'
    if ext in ['.wav']:
        return 'audio/wav'
    if ext in ['.ogg', '.oga']:
        return 'audio/ogg'
    if ext in ['.flac']:
        return 'audio/flac'
    if ext in ['.m4a', '.mp4', '.aac']:
        return 'audio/mp4'
    return 'application/octet-stream'

def get_related_tracks(current_track, limit=8):
    if not current_track.tags:
        return []
    current_tags = set(tag.strip().lower() for tag in current_track.tags.split(',') if tag.strip())
    other_tracks = Track.query.filter(Track.id != current_track.id).all()
    track_scores = []
    for track in other_tracks:
        if track.tags:
            track_tags = set(tag.strip().lower() for tag in track.tags.split(',') if tag.strip())
            common_tags = len(current_tags.intersection(track_tags))
            if common_tags > 0:
                track_scores.append((track, common_tags))
    track_scores.sort(key=lambda x: x[1], reverse=True)
    return [track for track, score in track_scores[:limit]]

@app.route('/artists')
def artists_index():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get all artists with their statistics
    artists_with_stats = []
    all_artists = Artist.query.all()
    
    for artist in all_artists:
        # Calculate total likes from tracks and videos
        track_likes = db.session.query(db.func.sum(Track.likes)).join(TrackArtist).filter(TrackArtist.artist_id == artist.id).scalar() or 0
        video_likes = db.session.query(db.func.sum(Video.likes)).join(VideoArtist).filter(VideoArtist.artist_id == artist.id).scalar() or 0
        total_likes = track_likes + video_likes
        
        # Calculate total plays from tracks and videos
        track_plays = db.session.query(db.func.sum(Track.view_count)).join(TrackArtist).filter(TrackArtist.artist_id == artist.id).scalar() or 0
        video_plays = db.session.query(db.func.sum(Video.view_count)).join(VideoArtist).filter(VideoArtist.artist_id == artist.id).scalar() or 0
        total_plays = track_plays + video_plays
        
        # Count tracks
        track_count = db.session.query(db.func.count(Track.id)).join(TrackArtist).filter(TrackArtist.artist_id == artist.id).scalar() or 0
        
        # Check if artist has avatar
        has_avatar = artist.avatar_path is not None and artist.avatar_path.strip() != ''
        
        artists_with_stats.append({
            'artist': artist,
            'total_likes': total_likes,
            'total_plays': total_plays,
            'track_count': track_count,
            'has_avatar': has_avatar
        })
    
    # Sort by: total_likes (desc), track_count (desc), has_avatar (desc), name (asc)
    artists_with_stats.sort(key=lambda x: (-x['total_likes'], -x['track_count'], -x['has_avatar'], x['artist'].name))
    
    # Apply pagination manually
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_artists_with_stats = artists_with_stats[start_idx:end_idx]
    total_pages = (len(artists_with_stats) + per_page - 1) // per_page
    
    return render_template('artists.html', artists_with_stats=paginated_artists_with_stats, page=page, total_pages=total_pages)

@app.route('/tracks')
def tracks_index():
    page = request.args.get('page', 1, type=int)
    artist = request.args.get('artist')
    sort_by = request.args.get('sort', 'newest')
    per_page = 20
    
    # Base query for tracks
    query = Track.query
    
    # Filter by artist if specified
    if artist:
        query = query.join(TrackArtist).join(Artist).filter(Artist.name.ilike(f'%{artist}%'))
    
    # Apply sorting
    if sort_by == 'newest':
        query = query.order_by(desc(Track.id))
    elif sort_by == 'oldest':
        query = query.order_by(Track.id)
    elif sort_by == 'most_viewed':
        query = query.order_by(desc(Track.view_count))
    elif sort_by == 'most_liked':
        query = query.order_by(desc(Track.likes))
    
    tracks = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get artists for each track
    track_artists = {}
    for track in tracks.items:
        track_artists[track.id] = db.session.query(Artist).join(TrackArtist).filter(TrackArtist.track_id == track.id).all()
    
    return render_template('tracks.html', 
                         tracks=tracks.items, 
                         page=page, 
                         total_pages=tracks.pages,
                         artist=artist,
                         sort_by=sort_by,
                         track_artists=track_artists)

@app.route('/artist/<int:artist_id>')
def artist_detail(artist_id):
    artist = Artist.query.get_or_404(artist_id)
    tracks = db.session.query(Track).join(TrackArtist, TrackArtist.track_id == Track.id).filter(TrackArtist.artist_id == artist_id).order_by(desc(Track.id)).all()
    videos = db.session.query(Video).join(VideoArtist, VideoArtist.video_id == Video.id).filter(VideoArtist.artist_id == artist_id).order_by(desc(Video.id)).all()
    
    # Calculate artist statistics
    total_tracks = len(tracks)
    total_videos = len(videos)
    total_plays = sum((t.view_count or 0) for t in tracks) + sum((v.view_count or 0) for v in videos)
    total_likes = sum((t.likes or 0) for t in tracks) + sum((v.likes or 0) for v in videos)
    
    # Get artist comments
    artist_comments = ArtistComment.query.filter_by(artist_id=artist_id).order_by(ArtistComment.timestamp.desc()).all()
    
    # Get track comments for this artist's tracks
    track_comment_data = []
    if tracks:
        track_ids = [t.id for t in tracks]
        track_comments = TrackComment.query.filter(TrackComment.track_id.in_(track_ids)).order_by(TrackComment.timestamp.desc()).all()
        
        # Create a mapping of track_id to track for easy lookup
        track_map = {t.id: t for t in tracks}
        
        for comment in track_comments:
            track = track_map.get(comment.track_id)
            if track:
                track_comment_data.append({
                    'comment': comment,
                    'track': track
                })
    
    # Get recent activity (comments made by this artist across all entities)
    recent_activity = []
    
    # Get all comments by this artist across different entities
    video_comments = Comment.query.filter_by(author=artist.name).order_by(desc(Comment.timestamp)).limit(10).all()
    playlist_comments = PlaylistComment.query.filter_by(author=artist.name).order_by(desc(PlaylistComment.timestamp)).limit(10).all()
    tag_comments = TagComment.query.filter_by(author=artist.name).order_by(desc(TagComment.timestamp)).limit(10).all()
    track_comments_by_artist = TrackComment.query.filter_by(author=artist.name).order_by(desc(TrackComment.timestamp)).limit(10).all()
    
    # Process video comments
    if video_comments:
        video_id_to_video = {v.id: v for v in Video.query.filter(Video.id.in_({c.video_id for c in video_comments})).all()}
        for c in video_comments:
            video = video_id_to_video.get(c.video_id)
            recent_activity.append({
                'kind': 'video',
                'content': c.content,
                'timestamp': c.timestamp,
                'likes': c.likes or 0,
                'context_title': (video.nickname or video.original_filepath) if video else f"Video {c.video_id}",
                'context_url': url_for('video.video_detail', video_id=c.video_id)
            })
    
    # Process playlist comments
    if playlist_comments:
        playlist_id_to_playlist = {p.id: p for p in Playlist.query.filter(Playlist.id.in_({c.playlist_id for c in playlist_comments})).all()}
        for c in playlist_comments:
            playlist = playlist_id_to_playlist.get(c.playlist_id)
            recent_activity.append({
                'kind': 'playlist',
                'content': c.content,
                'timestamp': c.timestamp,
                'likes': c.likes or 0,
                'context_title': playlist.name if playlist else f"Playlist {c.playlist_id}",
                'context_url': url_for('playlist_detail', playlist_id=c.playlist_id)
            })
    
    # Process tag comments
    for c in tag_comments:
        recent_activity.append({
            'kind': 'tag',
            'content': c.content,
            'timestamp': c.timestamp,
            'likes': c.likes or 0,
            'context_title': f"#{c.tag_name}",
            'context_url': url_for('tag_detail', tag=c.tag_name)
        })
    
    # Process track comments
    if track_comments_by_artist:
        track_id_to_track = {t.id: t for t in Track.query.filter(Track.id.in_({c.track_id for c in track_comments_by_artist})).all()}
        for c in track_comments_by_artist:
            track = track_id_to_track.get(c.track_id)
            recent_activity.append({
                'kind': 'track',
                'content': c.content,
                'timestamp': c.timestamp,
                'likes': c.likes or 0,
                'context_title': (track.nickname or track.original_filepath) if track else f"Track {c.track_id}",
                'context_url': url_for('track_detail', track_id=c.track_id)
            })
    
    # Sort by timestamp desc
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:20]  # Limit to 20 most recent activities
    
    # Get author avatars for all comments
    all_comment_authors = set()
    for comment in artist_comments:
        all_comment_authors.add(slugify_author(comment.author))
    for data in track_comment_data:
        all_comment_authors.add(slugify_author(data['comment'].author))
    
    author_avatars = {}
    if all_comment_authors:
        profiles = AuthorProfile.query.filter(AuthorProfile.slug.in_(all_comment_authors)).all()
        for profile in profiles:
            if profile.avatar_path:
                author_avatars[profile.slug] = profile.avatar_path
    
    # Get playlists that contain this artist's content (simplified)
    artist_playlists = []
    
    # Get related artists (simplified approach - just get other artists)
    related_artists = Artist.query.filter(Artist.id != artist_id).limit(6).all()
    
    return render_template('artist_detail.html', 
                         artist=artist, 
                         tracks=tracks, 
                         videos=videos,
                         total_tracks=total_tracks,
                         total_videos=total_videos,
                         total_plays=total_plays,
                         total_likes=total_likes,
                         artist_playlists=artist_playlists,
                         related_artists=related_artists,
                         artist_comments=artist_comments,
                         track_comment_data=track_comment_data,
                         author_avatars=author_avatars,
                         recent_activity=recent_activity)

@app.route('/add_artist', methods=['GET', 'POST'])
def add_artist():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        bio = request.form.get('bio')
        avatar = request.files.get('avatar')
        if not name:
            return jsonify({"error": "Artist name is required"}), 400
        try:
            existing = Artist.query.filter(Artist.name.ilike(name)).first()
            if existing:
                return jsonify({"success": True, "artist_id": existing.id}), 200
            avatar_path_rel = None
            if avatar and avatar.filename:
                ext = os.path.splitext(avatar.filename)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    filename = secure_filename(f"avatar_{uuid.uuid4().hex}{ext}")
                    abs_path = os.path.join(app.config['AVATAR_FOLDER'], filename)
                    os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)
                    avatar.save(abs_path)
                    avatar_path_rel = os.path.join('avatars', filename).replace('\\', '/')
            artist = Artist(name=name, bio=bio, avatar_path=avatar_path_rel)
            db.session.add(artist)
            db.session.commit()
            return jsonify({"success": True, "artist_id": artist.id}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
    return render_template('add_artist.html')


@app.route('/add_track', methods=['GET', 'POST'])
def add_track():
    if request.method == 'POST':
        file = request.files.get('file')
        background = request.files.get('background')
        nickname = request.form.get('nickname')
        artist_name = request.form.get('artist_name', '').strip()
        description = request.form.get('description')
        tags = request.form.get('tags')
        stealth = request.form.get('stealth') == 'on'

        if not file or file.filename == '':
            return jsonify({"error": "No audio file provided"}), 400

        original_filepath = file.filename
        original_extension = os.path.splitext(original_filepath)[1].lower()
        allowed_audio_exts = ['.mp3', '.wav', '.ogg', '.oga', '.flac', '.m4a', '.aac']
        if original_extension not in allowed_audio_exts:
            return jsonify({"error": "Unsupported audio format"}), 400

        base_filename = secure_filename((nickname or os.path.splitext(original_filepath)[0]) + original_extension)
        upload_folder = app.config['STEALTH_AUDIO_UPLOAD_FOLDER'] if stealth else app.config['AUDIO_UPLOAD_FOLDER']
        new_filename, stored_filepath = generate_unique_filename(base_filename, upload_folder)

        try:
            os.makedirs(upload_folder, exist_ok=True)
            file.save(stored_filepath)

            # Optional background image upload
            relative_cover_path = None
            if background and background.filename:
                cover_ext = os.path.splitext(background.filename)[1].lower()
                if cover_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    cover_filename = secure_filename(f"cover_{os.path.splitext(new_filename)[0]}{cover_ext}")
                    cover_path = os.path.join(app.config['COVER_FOLDER'], cover_filename)
                    os.makedirs(app.config['COVER_FOLDER'], exist_ok=True)
                    background.save(cover_path)
                    relative_cover_path = os.path.join('covers', cover_filename).replace('\\', '/')

            new_track = Track(
                original_filepath=original_filepath,
                stored_filepath=stored_filepath,
                nickname=nickname,
                description=description,
                tags=tags,
                background_image_path=relative_cover_path,
                view_count=0,
                likes=0,
            )
            db.session.add(new_track)
            # Optional artist association (create if missing)
            if artist_name:
                artist = Artist.query.filter(Artist.name.ilike(artist_name)).first()
                if not artist:
                    artist = Artist(name=artist_name)
                    db.session.add(artist)
                    db.session.flush()
                db.session.add(TrackArtist(track_id=new_track.id, artist_id=artist.id))
            db.session.commit()

            return jsonify({"success": True, "track_id": new_track.id}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    # GET: show upload form
    return render_template('add_track.html')

@app.route('/stream_track/<int:track_id>')
def stream_track(track_id):
    track = Track.query.get_or_404(track_id)
    mime_type = get_mime_type_for_audio(track.stored_filepath)
    range_header = request.headers.get('Range', None)
    file_size = os.path.getsize(track.stored_filepath)
    if range_header:
        byte1, byte2 = 0, None
        match = re.search(r'(\d+)-(\d*)', range_header)
        groups = match.groups()
        if groups[0]:
            byte1 = int(groups[0])
        if groups[1]:
            byte2 = int(groups[1])
        if byte2 is None:
            byte2 = file_size - 1
        length = byte2 - byte1 + 1
        with open(track.stored_filepath, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)
        resp = make_response(data)
        resp.headers.set('Content-Type', mime_type)
        resp.headers.set('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        resp.headers.set('Accept-Ranges', 'bytes')
        resp.headers.set('Content-Length', str(length))
        return resp, 206
    else:
        return send_file(track.stored_filepath, mimetype=mime_type)

@app.route('/track/<int:track_id>')
def track_detail(track_id):
    track = Track.query.get_or_404(track_id)
    track.view_count = (track.view_count or 0) + 1
    related_tracks = get_related_tracks(track)
    comments = TrackComment.query.filter_by(track_id=track_id).order_by(TrackComment.timestamp.desc()).all()
    author_slugs = {slugify_author(c.author) for c in comments}
    avatars = {}
    if author_slugs:
        profiles = AuthorProfile.query.filter(AuthorProfile.slug.in_(author_slugs)).all()
        for p in profiles:
            if p.avatar_path:
                avatars[p.slug] = p.avatar_path
    artists = db.session.query(Artist).join(TrackArtist, TrackArtist.artist_id == Artist.id).filter(TrackArtist.track_id == track_id).all()
    db.session.commit()
    return render_template('track_detail.html', track=track, related_tracks=related_tracks, comments=comments, artists=artists, author_avatars=avatars)

@app.route('/like_track/<int:track_id>', methods=['POST'])
def like_track(track_id):
    track = Track.query.get_or_404(track_id)
    track.likes = (track.likes or 0) + 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": track.likes})

@app.route('/increment_track_view/<int:track_id>', methods=['POST'])
def increment_track_view(track_id):
    track = Track.query.get_or_404(track_id)
    if track.view_count is None:
        track.view_count = 1
    else:
        track.view_count += 1
    db.session.commit()
    return jsonify({"success": True, "new_view_count": track.view_count})

@app.route('/add_track_comment/<int:track_id>', methods=['POST'])
def add_track_comment(track_id):
    track = Track.query.get_or_404(track_id)
    author = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()
    if not author or not content:
        return jsonify({"error": "Name and comment are required"}), 400
    try:
        # Get or create artist for the comment author
        artist = get_or_create_artist_by_name(author)
        
        comment = TrackComment(track_id=track_id, author=author, content=content, likes=0, author_artist_id=artist.id if artist else None)
        db.session.add(comment)
        db.session.commit()
        author_slug = slugify_author(comment.author)
        profile = AuthorProfile.query.filter_by(slug=author_slug).first()
        avatar_rel = profile.avatar_path if profile and profile.avatar_path else None

        return jsonify({
            "success": True,
            "comment": {
                "id": comment.id,
                "author": comment.author,
                "author_slug": author_slug,
                "author_avatar": avatar_rel,
                "author_artist_id": artist.id if artist else None,
                "content": comment.content,
                "timestamp": comment.timestamp.strftime("%m/%d/%Y %I:%M %p"),
                "likes": comment.likes
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/like_track_comment/<int:comment_id>', methods=['POST'])
def like_track_comment(comment_id):
    comment = TrackComment.query.get_or_404(comment_id)
    comment.likes = (comment.likes or 0) + 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": comment.likes})

@app.route('/delete_track_comment/<int:comment_id>', methods=['POST'])
def delete_track_comment(comment_id):
    comment = TrackComment.query.get_or_404(comment_id)
    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/add_artist_comment/<int:artist_id>', methods=['POST'])
def add_artist_comment(artist_id):
    artist = Artist.query.get_or_404(artist_id)
    author = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()
    if not author or not content:
        return jsonify({"error": "Name and comment are required"}), 400
    try:
        # Get or create artist for the comment author
        comment_artist = get_or_create_artist_by_name(author)
        
        comment = ArtistComment(artist_id=artist_id, author=author, content=content, likes=0, author_artist_id=comment_artist.id if comment_artist else None)
        db.session.add(comment)
        db.session.commit()
        author_slug = slugify_author(comment.author)
        profile = AuthorProfile.query.filter_by(slug=author_slug).first()
        avatar_rel = profile.avatar_path if profile and profile.avatar_path else None

        return jsonify({
            "success": True,
            "comment": {
                "id": comment.id,
                "author": comment.author,
                "author_slug": author_slug,
                "author_avatar": avatar_rel,
                "author_artist_id": comment_artist.id if comment_artist else None,
                "content": comment.content,
                "timestamp": comment.timestamp.strftime("%m/%d/%Y %I:%M %p"),
                "likes": comment.likes
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/like_artist_comment/<int:comment_id>', methods=['POST'])
def like_artist_comment(comment_id):
    comment = ArtistComment.query.get_or_404(comment_id)
    comment.likes = (comment.likes or 0) + 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": comment.likes})

@app.route('/delete_artist_comment/<int:comment_id>', methods=['POST'])
def delete_artist_comment(comment_id):
    comment = ArtistComment.query.get_or_404(comment_id)
    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<int:artist_id>/bio', methods=['POST'])
def update_artist_bio(artist_id):
    artist = Artist.query.get_or_404(artist_id)
    bio = request.form.get('bio', '').strip()
    
    try:
        artist.bio = bio
        db.session.commit()
        
        # Convert markdown to HTML for preview
        bio_html = markdown.markdown(bio, extensions=['nl2br', 'fenced_code']) if bio else ''
        
        return jsonify({
            "success": True,
            "bio": bio,
            "bio_html": bio_html
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# AI Comment Generation Endpoints
@app.route('/generate_track_comment/<int:track_id>', methods=['POST'])
def generate_track_comment(track_id):
    """Generate an AI comment for a track"""
    try:
        track = Track.query.get_or_404(track_id)
        
        # Get the prompt from the request
        prompt = request.json.get('prompt', '') if request.is_json else request.form.get('prompt', '')
        
        # Get track artists
        track_artists = [artist.name for artist in track.artists]
        artist_name = track_artists[0] if track_artists else "Unknown Artist"
        
        # Generate the comment using AI
        ai_generator = get_ai_generator()
        result = ai_generator.generate_track_comment(
            track_name=track.nickname or track.original_filepath,
            artist_name=artist_name,
            custom_prompt=prompt if prompt else None,
            track_tags=track.tags
        )
        
        # Debug logging
        print(f"AI Generation Result: {result}")
        
        if result['success']:
            response_data = {
                "success": True,
                "comment": result['comment'],
                "prompt_used": result['prompt_used']
            }
            print(f"Returning success response: {response_data}")
            return jsonify(response_data)
        else:
            error_response = {
                "success": False,
                "error": result['error']
            }
            print(f"Returning error response: {error_response}")
            return jsonify(error_response), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/generate_artist_comment/<int:artist_id>', methods=['POST'])
def generate_artist_comment(artist_id):
    """Generate an AI comment for an artist"""
    try:
        artist = Artist.query.get_or_404(artist_id)
        
        # Get the prompt from the request
        prompt = request.json.get('prompt', '') if request.is_json else request.form.get('prompt', '')
        
        # Count tracks by this artist
        track_count = Track.query.join(TrackArtist).filter(TrackArtist.c.artist_id == artist_id).count()
        
        # Generate the comment using AI
        ai_generator = get_ai_generator()
        result = ai_generator.generate_artist_comment(
            artist_name=artist.name,
            custom_prompt=prompt if prompt else None,
            artist_bio=artist.bio,
            track_count=track_count
        )
        
        if result['success']:
            return jsonify({
                "success": True,
                "comment": result['comment'],
                "prompt_used": result['prompt_used']
            })
        else:
            return jsonify({
                "success": False,
                "error": result['error']
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/ai_comment_prompts')
def get_ai_comment_prompts():
    """Get available AI comment prompts"""
    try:
        ai_generator = get_ai_generator()
        prompts = ai_generator.get_default_prompts()
        return jsonify({
            "success": True,
            "prompts": prompts
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'newest')  # Default sort by newest
    per_page = 10

    # Get both videos and tracks
    video_query = Video.query
    track_query = Track.query

    # Apply sorting to videos
    if sort_by == 'newest':
        video_query = video_query.order_by(desc(Video.id))
        track_query = track_query.order_by(desc(Track.id))
    elif sort_by == 'oldest':
        video_query = video_query.order_by(Video.id)
        track_query = track_query.order_by(Track.id)
    elif sort_by == 'most_viewed':
        video_query = video_query.order_by(desc(Video.view_count))
        track_query = track_query.order_by(desc(Track.view_count))
    elif sort_by == 'most_liked':
        video_query = video_query.order_by(desc(Video.likes))
        track_query = track_query.order_by(desc(Track.likes))

    # Get all videos and tracks
    all_videos = video_query.all()
    all_tracks = track_query.all()
    
    # Combine and sort by creation time (using id as proxy)
    combined_content = []
    
    # Add videos with type indicator
    for video in all_videos:
        combined_content.append({
            'type': 'video',
            'id': video.id,
            'object': video,
            'sort_key': video.id
        })
    
    # Add tracks with type indicator
    for track in all_tracks:
        combined_content.append({
            'type': 'track',
            'id': track.id,
            'object': track,
            'sort_key': track.id
        })
    
    # Sort combined content by sort_key (id) in descending order for newest first
    if sort_by == 'newest':
        combined_content.sort(key=lambda x: x['sort_key'], reverse=True)
    elif sort_by == 'oldest':
        combined_content.sort(key=lambda x: x['sort_key'])
    elif sort_by == 'most_viewed':
        combined_content.sort(key=lambda x: x['object'].view_count or 0, reverse=True)
    elif sort_by == 'most_liked':
        combined_content.sort(key=lambda x: x['object'].likes or 0, reverse=True)
    
    # Manual pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_content = combined_content[start_idx:end_idx]
    
    # Calculate total pages
    total_items = len(combined_content)
    total_pages = (total_items + per_page - 1) // per_page
    
    return render_template('index.html', 
                         content=paginated_content, 
                         page=page, 
                         total_pages=total_pages, 
                         tag=None,
                         sort_by=sort_by)

# Route moved to video_routes.py blueprint

@app.route('/stream/<int:video_id>')
def stream_video(video_id):
    video = Video.query.get_or_404(video_id)
    
    # Determine mime type based on file extension
    file_extension = os.path.splitext(video.stored_filepath)[1].lower()
    mime_type = 'video/webm' if file_extension == '.webm' else 'video/mp4'
    
    range_header = request.headers.get('Range', None)
    file_size = os.path.getsize(video.stored_filepath)

    if range_header:
        byte1, byte2 = 0, None
        match = re.search(r'(\d+)-(\d*)', range_header)
        groups = match.groups()

        if groups[0]:
            byte1 = int(groups[0])
        if groups[1]:
            byte2 = int(groups[1])

        if byte2 is None:
            byte2 = file_size - 1
        length = byte2 - byte1 + 1

        with open(video.stored_filepath, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)

        resp = make_response(data)
        resp.headers.set('Content-Type', mime_type)  # Use dynamic mime type
        resp.headers.set('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        resp.headers.set('Accept-Ranges', 'bytes')
        resp.headers.set('Content-Length', str(length))
        return resp, 206
    else:
        return send_file(video.stored_filepath, mimetype=mime_type)  # Use dynamic mime type

@app.route('/filter')
def filter_videos():
    tag = request.args.get('tag')
    
    # If a tag is provided, redirect to the dedicated tag page
    if tag:
        return redirect(url_for('tag_detail', tag=tag))
    
    # Otherwise, continue with the existing filtering logic
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'newest')
    per_page = 10

    # Get both videos and tracks
    video_query = Video.query
    track_query = Track.query

    # Apply sorting to videos
    if sort_by == 'newest':
        video_query = video_query.order_by(desc(Video.id))
        track_query = track_query.order_by(desc(Track.id))
    elif sort_by == 'oldest':
        video_query = video_query.order_by(Video.id)
        track_query = track_query.order_by(Track.id)
    elif sort_by == 'most_viewed':
        video_query = video_query.order_by(desc(Video.view_count))
        track_query = track_query.order_by(desc(Track.view_count))
    elif sort_by == 'most_liked':
        video_query = video_query.order_by(desc(Video.likes))
        track_query = track_query.order_by(desc(Track.likes))

    # Get all videos and tracks
    all_videos = video_query.all()
    all_tracks = track_query.all()
    
    # Combine and sort by creation time (using id as proxy)
    combined_content = []
    
    # Add videos with type indicator
    for video in all_videos:
        combined_content.append({
            'type': 'video',
            'id': video.id,
            'object': video,
            'sort_key': video.id
        })
    
    # Add tracks with type indicator
    for track in all_tracks:
        combined_content.append({
            'type': 'track',
            'id': track.id,
            'object': track,
            'sort_key': track.id
        })
    
    # Sort combined content by sort_key (id) in descending order for newest first
    if sort_by == 'newest':
        combined_content.sort(key=lambda x: x['sort_key'], reverse=True)
    elif sort_by == 'oldest':
        combined_content.sort(key=lambda x: x['sort_key'])
    elif sort_by == 'most_viewed':
        combined_content.sort(key=lambda x: x['object'].view_count or 0, reverse=True)
    elif sort_by == 'most_liked':
        combined_content.sort(key=lambda x: x['object'].likes or 0, reverse=True)
    
    # Manual pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_content = combined_content[start_idx:end_idx]
    
    # Calculate total pages
    total_items = len(combined_content)
    total_pages = (total_items + per_page - 1) // per_page
    
    return render_template('index.html', 
                         content=paginated_content, 
                         page=page, 
                         total_pages=total_pages,
                         tag=tag,
                         sort_by=sort_by)

@app.route('/delete/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    try:
        # Delete the file
        if os.path.exists(video.stored_filepath):
            os.remove(video.stored_filepath)
        
        # Delete the database entry
        db.session.delete(video)
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/delete_track/<int:track_id>', methods=['POST'])
def delete_track(track_id):
    track = Track.query.get_or_404(track_id)
    try:
        # Delete the file
        if os.path.exists(track.stored_filepath):
            os.remove(track.stored_filepath)
        
        # Delete the database entry
        db.session.delete(track)
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/edit_tags/<int:video_id>', methods=['POST'])
def edit_tags(video_id):
    video = Video.query.get_or_404(video_id)
    new_tags = request.form.get('tags')
    
    try:
        video.tags = new_tags
        db.session.commit()
        return jsonify({"success": True, "new_tags": new_tags}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

def get_related_videos(current_video, limit=8):
    if not current_video.tags:
        return []
    
    current_tags = set(tag.strip().lower() for tag in current_video.tags.split(',') if tag.strip())
    
    # Get all videos except the current one
    other_videos = Video.query.filter(Video.id != current_video.id).all()
    
    # Calculate similarity scores
    video_scores = []
    for video in other_videos:
        if video.tags:
            video_tags = set(tag.strip().lower() for tag in video.tags.split(',') if tag.strip())
            common_tags = len(current_tags.intersection(video_tags))
            if common_tags > 0:
                video_scores.append((video, common_tags))
    
    # Sort by number of common tags (descending)
    video_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Return the top N videos
    return [video for video, score in video_scores[:limit]]

# Route moved to video_routes.py blueprint

@app.route('/edit_description/<int:video_id>', methods=['POST'])
def edit_description(video_id):
    video = Video.query.get_or_404(video_id)
    new_description = request.form.get('description')
    
    try:
        video.description = new_description
        db.session.commit()
        return jsonify({"success": True, "new_description": new_description}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/get_tags')
def get_tags():
    tags = db.session.query(
        func.trim(func.lower(func.substr(Video.tags, 1, func.instr(Video.tags + ',', ',') - 1))).cast(db.String).label('tag'),
        func.count('*').label('count')
    ).group_by('tag').order_by(desc('count')).all()
    
    return jsonify([{'tag': tag, 'count': count} for tag, count in tags])

@app.route('/get_tag_suggestions')
def get_tag_suggestions():
    query = request.args.get('q', '').lower()
    all_tags = db.session.query(
        func.trim(func.lower(func.substr(Video.tags, 1, func.instr(Video.tags + ',', ',') - 1))).label('tag')
    ).distinct().all()
    
    # Filter out None values and then check for matches
    matching_tags = [tag[0] for tag in all_tags if tag[0] is not None and query in tag[0].lower()]
    matching_tags.sort(key=lambda x: x.lower().index(query))  # Sort by relevance
    return jsonify(matching_tags[:10])  # Return top 10 matches

@app.route('/thumbnail/<int:video_id>')
def serve_thumbnail(video_id):
    video = Video.query.get_or_404(video_id)
    thumbnail_path = os.path.join(app.static_folder, video.thumbnail_path)
    return send_file(thumbnail_path, mimetype='image/jpeg')

@app.route('/increment_view/<int:video_id>', methods=['POST'])
def increment_view(video_id):
    video = Video.query.get_or_404(video_id)
    if video.view_count is None:
        video.view_count = 1
    else:
        video.view_count += 1
    db.session.commit()
    return jsonify({"success": True, "new_view_count": video.view_count})

@app.route('/bulk_upload', methods=['GET', 'POST'])
def bulk_upload():
    if request.method == 'POST':
        uploaded_files = request.files.getlist('files')
        
        if not uploaded_files:
            return jsonify({"error": "No files provided"}), 400
        
        successful_uploads = 0
        errors = []

        for file in uploaded_files:
            if isinstance(file, FileStorage) and file.filename != '':
                original_extension = os.path.splitext(file.filename)[1].lower()
                if original_extension not in ['.mp4', '.webm']:
                    errors.append(f"Skipped {file.filename}: Only MP4 and WebM files are allowed")
                    continue

                try:
                    new_filename, stored_filepath = generate_unique_filename(
                        file.filename, 
                        app.config['STEALTH_UPLOAD_FOLDER']
                    )
                    
                    os.makedirs(app.config['STEALTH_UPLOAD_FOLDER'], exist_ok=True)
                    file.save(stored_filepath)
                    
                    # Convert WebM to MP4 if necessary
                    if original_extension == '.webm':
                        stored_filepath = convert_webm_to_mp4(stored_filepath)
                        new_filename = os.path.basename(stored_filepath)

                    # Generate thumbnail
                    thumbnail_filename = f"thumbnail_{os.path.splitext(new_filename)[0]}.jpg"
                    thumbnails_dir = os.path.join(app.static_folder, 'thumbnails')
                    os.makedirs(thumbnails_dir, exist_ok=True)
                    thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)
                    
                    # Get video duration more robustly
                    probe = ffmpeg.probe(stored_filepath)
                    duration = None
                    # Try different methods to get duration
                    for stream in probe['streams']:
                        if 'duration' in stream:
                            duration = float(stream['duration'])
                            break
                    
                    # If duration not found in streams, try format
                    if duration is None and 'format' in probe and 'duration' in probe['format']:
                        duration = float(probe['format']['duration'])
                    
                    # If still no duration, use a default timestamp
                    if duration is None:
                        duration = 0
                    
                    # Extract middle frame
                    (
                        ffmpeg
                        .input(stored_filepath, ss=duration/2 if duration > 0 else 0)
                        .filter('scale', 320, -1)
                        .output(thumbnail_path, vframes=1)
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True)
                    )
                    
                    # Set the thumbnail_path to be relative to the static folder
                    relative_thumbnail_path = os.path.join('thumbnails', thumbnail_filename).replace('\\', '/')
                    
                    new_video = Video(
                        original_filepath=file.filename, 
                        stored_filepath=stored_filepath,
                        thumbnail_path=relative_thumbnail_path,
                        view_count=0
                    )
                    db.session.add(new_video)
                    successful_uploads += 1
                except Exception as e:
                    errors.append(f"Error uploading {file.filename}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "uploaded": successful_uploads,
            "errors": errors
        }), 200

    return render_template('bulk_upload.html')

@app.route('/cleanup_stealth', methods=['POST'])
def cleanup_stealth():
    try:
        # Get all videos in stealth folder
        stealth_videos = Video.query.filter(
            Video.stored_filepath.like(f"{app.config['STEALTH_UPLOAD_FOLDER']}%")
        ).all()
        
        deleted_count = 0
        for video in stealth_videos:
            # Check if file exists
            if not os.path.exists(video.stored_filepath):
                # Delete thumbnail if it exists
                if video.thumbnail_path:
                    thumbnail_path = os.path.join(app.static_folder, video.thumbnail_path)
                    if os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)
                
                # Delete database entry
                db.session.delete(video)
                deleted_count += 1
        
        db.session.commit()
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Cleaned up {deleted_count} missing video entries"
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/like/<int:video_id>', methods=['POST'])
def like_video(video_id):
    video = Video.query.get_or_404(video_id)
    if video.likes is None:
        video.likes = 1
    else:
        video.likes += 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": video.likes})

@app.route('/add_comment/<int:video_id>', methods=['POST'])
def add_comment(video_id):
    video = Video.query.get_or_404(video_id)
    author = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()
    
    if not author or not content:
        return jsonify({"error": "Name and comment are required"}), 400
    
    try:
        # Get or create artist for the comment author
        artist = get_or_create_artist_by_name(author)
        
        comment = Comment(
            video_id=video_id,
            author=author,
            content=content,
            likes=0,
            author_artist_id=artist.id if artist else None
        )
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "comment": {
                "id": comment.id,
                "author": comment.author,
                "author_slug": slugify_author(comment.author),
                "author_artist_id": artist.id if artist else None,
                "content": comment.content,
                "timestamp": comment.timestamp.strftime("%m/%d/%Y %I:%M %p"),
                "likes": comment.likes
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/like_comment/<int:comment_id>', methods=['POST'])
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.likes is None:
        comment.likes = 1
    else:
        comment.likes += 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": comment.likes})

@app.route('/edit_title/<int:video_id>', methods=['POST'])
def edit_title(video_id):
    video = Video.query.get_or_404(video_id)
    new_title = request.json.get('title', '').strip()

    if not new_title:
        return jsonify({"error": "Title cannot be empty"}), 400

    try:
        video.nickname = new_title
        db.session.commit()
        return jsonify({"success": True, "new_title": new_title}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/move_to_regular/<int:video_id>', methods=['POST'])
def move_to_regular(video_id):
    video = Video.query.get_or_404(video_id)
    
    # Check if video is in stealth folder
    if not video.stored_filepath.startswith(app.config['STEALTH_UPLOAD_FOLDER']):
        return jsonify({"error": "Video is not in stealth uploads"}), 400
        
    try:
        # Create new filepath in regular uploads
        filename = os.path.basename(video.stored_filepath)
        new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Move the file
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.rename(video.stored_filepath, new_filepath)
        
        # Update database
        video.stored_filepath = new_filepath
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Video moved to regular uploads"
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    name = request.form.get('name')
    description = request.form.get('description', '')
    video_id = request.form.get('video_id')
    
    if not name:
        return jsonify({"error": "Playlist name is required"}), 400
        
    try:
        # Create the playlist first
        playlist = Playlist(name=name, description=description)
        db.session.add(playlist)
        db.session.flush()  # This assigns the ID to the playlist object
        
        # If video_id is provided, add it to the playlist
        if video_id:
            try:
                video_id = int(video_id)
                playlist_video = PlaylistVideo(
                    playlist_id=playlist.id,
                    video_id=video_id,
                    position=1
                )
                db.session.add(playlist_video)
            except ValueError:
                print(f"Invalid video_id: {video_id}")
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "playlist_id": playlist.id,
            "name": playlist.name
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error creating playlist: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500

@app.route('/add_to_playlist/<int:playlist_id>/<int:video_id>', methods=['POST'])
def add_to_playlist(playlist_id, video_id):
    try:
        # Get the last position in the playlist
        last_position = db.session.query(func.max(PlaylistVideo.position))\
            .filter_by(playlist_id=playlist_id).scalar() or 0
            
        playlist_video = PlaylistVideo(
            playlist_id=playlist_id,
            video_id=video_id,
            position=last_position + 1
        )
        db.session.add(playlist_video)
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/get_playlist/<int:playlist_id>')
def get_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    videos = db.session.query(Video, PlaylistVideo)\
        .join(PlaylistVideo)\
        .filter(PlaylistVideo.playlist_id == playlist_id)\
        .order_by(PlaylistVideo.position)\
        .all()
        
    return jsonify({
        "playlist": {
            "id": playlist.id,
            "name": playlist.name,
            "description": playlist.description,
            "videos": [{
                "id": video.id,
                "title": video.nickname or os.path.basename(video.original_filepath),
                "thumbnail": video.thumbnail_path,
                "position": pv.position,
                "description": video.description,
                "tags": video.tags,
                "view_count": video.view_count,
                "likes": video.likes
            } for video, pv in videos]
        }
    })

@app.route('/get_playlists')
def playlists():
    playlists = Playlist.query.order_by(desc(Playlist.created_at)).all()
    
    # Get video count and first thumbnail for each playlist
    playlist_info = []
    for playlist in playlists:
        # Convert Playlist object to dict with only the needed attributes
        playlist_dict = {
            'id': playlist.id,
            'name': playlist.name,
            'description': playlist.description,
            'created_at': playlist.created_at
        }
        
        video_count = PlaylistVideo.query.filter_by(playlist_id=playlist.id).count()
        
        # Get first video's thumbnail
        first_video = db.session.query(Video)\
            .join(PlaylistVideo)\
            .filter(PlaylistVideo.playlist_id == playlist.id)\
            .order_by(PlaylistVideo.position)\
            .first()
            
        thumbnail = first_video.thumbnail_path if first_video else None
        
        playlist_info.append({
            'playlist': playlist_dict,
            'video_count': video_count,
            'thumbnail': thumbnail
        })
    
    return render_template('playlists.html', playlists=playlist_info)

@app.route('/playlist/<int:playlist_id>')
def playlist_detail(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    playlist_videos = db.session.query(Video)\
        .join(PlaylistVideo)\
        .filter(PlaylistVideo.playlist_id == playlist_id)\
        .order_by(PlaylistVideo.position)\
        .all()
    
    # Add this line to get playlist comments
    comments = PlaylistComment.query.filter_by(playlist_id=playlist_id).order_by(PlaylistComment.timestamp.desc()).all()
    
    serialized_videos = [{
        'id': video.id,
        'nickname': video.nickname,
        'original_filepath': video.original_filepath,
        'thumbnail_path': video.thumbnail_path,
        'view_count': video.view_count or 0,
        'likes': video.likes or 0,
        'tags': video.tags
    } for video in playlist_videos]
    
    return render_template('playlist_detail.html', 
                         playlist=playlist, 
                         playlist_videos=playlist_videos,
                         serialized_videos=serialized_videos,
                         comments=comments)  # Add comments to template context

@app.route('/remove_from_playlist/<int:playlist_id>/<int:video_id>', methods=['POST'])
def remove_from_playlist(playlist_id, video_id):
    try:
        playlist_video = PlaylistVideo.query.filter_by(
            playlist_id=playlist_id,
            video_id=video_id
        ).first()
        
        if playlist_video:
            # Get the position of the removed video
            removed_position = playlist_video.position
            
            # Delete the playlist video entry
            db.session.delete(playlist_video)
            
            # Update positions of remaining videos
            PlaylistVideo.query.filter(
                PlaylistVideo.playlist_id == playlist_id,
                PlaylistVideo.position > removed_position
            ).update(
                {PlaylistVideo.position: PlaylistVideo.position - 1}
            )
            
            db.session.commit()
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": "Video not found in playlist"}), 404
            
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/edit_playlist/<int:playlist_id>', methods=['POST'])
def edit_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    data = request.json
    
    try:
        if 'name' in data:
            playlist.name = data['name']
        if 'description' in data:
            playlist.description = data['description']
            
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/add_playlist_comment/<int:playlist_id>', methods=['POST'])
def add_playlist_comment(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    author = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()
    
    if not author or not content:
        return jsonify({"error": "Name and comment are required"}), 400
    
    try:
        # Get or create artist for the comment author
        artist = get_or_create_artist_by_name(author)
        
        comment = PlaylistComment(
            playlist_id=playlist_id,
            author=author,
            content=content,
            likes=0,
            author_artist_id=artist.id if artist else None
        )
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "comment": {
                "id": comment.id,
                "author": comment.author,
                "author_slug": slugify_author(comment.author),
                "author_artist_id": artist.id if artist else None,
                "content": comment.content,
                "timestamp": comment.timestamp.strftime("%m/%d/%Y %I:%M %p"),
                "likes": comment.likes
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/like_playlist_comment/<int:comment_id>', methods=['POST'])
def like_playlist_comment(comment_id):
    comment = PlaylistComment.query.get_or_404(comment_id)
    if comment.likes is None:
        comment.likes = 1
    else:
        comment.likes += 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": comment.likes})

@app.route('/api/playlists')
def get_playlists_json():
    playlists = Playlist.query.order_by(desc(Playlist.created_at)).all()
    return jsonify([{
        'playlist': {
            'id': playlist.id,
            'name': playlist.name,
            'description': playlist.description,
            'created_at': playlist.created_at.isoformat() if playlist.created_at else None
        }
    } for playlist in playlists])

@app.route('/delete_playlist_comment/<int:comment_id>', methods=['POST'])
def delete_playlist_comment(comment_id):
    comment = PlaylistComment.query.get_or_404(comment_id)
    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/add_multiple', methods=['GET', 'POST'])
def add_multiple_videos():
    if request.method == 'POST':
        files = request.files.getlist('files')
        playlist_name = request.form.get('playlist_name')
        apply_to_videos = request.form.get('apply_to_videos') == 'on'
        description = request.form.get('description')
        tags = request.form.get('tags')
        stealth = request.form.get('stealth') == 'on'
        
        if not files:
            return jsonify({"error": "No files provided"}), 400
            
        try:
            # Create playlist first if name provided
            playlist = None
            if playlist_name:
                playlist = Playlist(name=playlist_name, description=description)
                db.session.add(playlist)
                db.session.flush()  # Get playlist ID
            
            uploaded_videos = []
            for idx, file in enumerate(files, 1):
                if not file or not file.filename:
                    continue
                    
                # Generate video nickname based on playlist name and/or tags
                video_nickname = None
                if playlist_name and apply_to_videos:
                    if tags:
                        video_nickname = f"{playlist_name} - {' '.join(tag.strip() for tag in tags.split(','))} {idx}"
                    else:
                        video_nickname = f"{playlist_name} - {idx}"
                elif tags:
                    tag_list = [tag.strip() for tag in tags.split(',')]
                    timestamp = datetime.now().strftime('%H%M%S')
                    video_nickname = f"{' '.join(tag_list)} {timestamp}_{idx}"
                
                # Use existing upload logic
                original_filepath = file.filename
                original_extension = os.path.splitext(original_filepath)[1]
                
                if video_nickname:
                    base_filename = secure_filename(video_nickname + original_extension)
                else:
                    base_filename = secure_filename(original_filepath)
                
                upload_folder = app.config['STEALTH_UPLOAD_FOLDER'] if stealth else app.config['UPLOAD_FOLDER']
                new_filename, stored_filepath = generate_unique_filename(base_filename, upload_folder)
                
                # Save and process video file (similar to add_video route)
                os.makedirs(upload_folder, exist_ok=True)
                file.save(stored_filepath)
                
                if original_extension == '.webm':
                    stored_filepath = convert_webm_to_mp4(stored_filepath)
                    new_filename = os.path.basename(stored_filepath)
                
                # Generate thumbnail (reuse existing thumbnail generation code)
                thumbnail_filename = f"thumbnail_{os.path.splitext(new_filename)[0]}.jpg"
                thumbnails_dir = os.path.join(app.static_folder, 'thumbnails')
                os.makedirs(thumbnails_dir, exist_ok=True)
                thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)
                
                # Extract thumbnail (reuse existing thumbnail extraction code)
                probe = ffmpeg.probe(stored_filepath)
                duration = next((float(stream['duration']) for stream in probe['streams'] 
                              if 'duration' in stream), None) or 0
                
                (
                    ffmpeg
                    .input(stored_filepath, ss=duration/2 if duration > 0 else 0)
                    .filter('scale', 320, -1)
                    .output(thumbnail_path, vframes=1)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                
                relative_thumbnail_path = os.path.join('thumbnails', thumbnail_filename).replace('\\', '/')
                
                # Create video entry
                new_video = Video(
                    original_filepath=original_filepath,
                    stored_filepath=stored_filepath,
                    nickname=video_nickname,
                    description=description,
                    tags=tags,
                    thumbnail_path=relative_thumbnail_path,
                    view_count=0
                )
                db.session.add(new_video)
                db.session.flush()  # Get video ID
                
                # Add to playlist if one was created
                if playlist:
                    playlist_video = PlaylistVideo(
                        playlist_id=playlist.id,
                        video_id=new_video.id,
                        position=idx
                    )
                    db.session.add(playlist_video)
                
                uploaded_videos.append(new_video.id)
            
            db.session.commit()
            
            response_data = {
                "success": True,
                "videos": uploaded_videos
            }
            if playlist:
                response_data["playlist_id"] = playlist.id
                
            return jsonify(response_data), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
    
    # GET request - show upload form
    recent_tags = db.session.query(
        Video.tags, Video.id
    ).order_by(
        desc(Video.id)
    ).limit(20).all()
    
    processed_tags = []
    seen_tags = set()
    
    for video_tags, _ in recent_tags:
        if video_tags:
            tags_list = [tag.strip() for tag in video_tags.split(',')]
            for tag in tags_list:
                if tag and tag.lower() not in seen_tags:
                    seen_tags.add(tag.lower())
                    processed_tags.append(tag)
    
    return render_template('add_multiple.html', recent_tags=processed_tags[:20])

@app.route('/extract_mp3', methods=['GET', 'POST'])
def extract_mp3():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "No file provided"}), 400
            
        try:
            # Generate unique filename for the input file
            input_filename = secure_filename(file.filename)
            input_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{input_filename}")
            
            # Generate output filename (change extension to .mp3)
            output_filename = os.path.splitext(input_filename)[0] + '.mp3'
            output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            
            # Save uploaded file
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(input_filepath)
            
            # Extract audio using ffmpeg
            try:
                (
                    ffmpeg
                    .input(input_filepath)
                    .output(output_filepath, acodec='libmp3lame', ab='192k')
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                
                # Clean up the input file
                os.remove(input_filepath)
                
                # Send the MP3 file
                return send_file(
                    output_filepath,
                    mimetype='audio/mpeg',
                    as_attachment=True,
                    download_name=output_filename
                )
                
            except ffmpeg.Error as e:
                return jsonify({"error": f"FFmpeg error: {e.stderr.decode()}"}), 500
            finally:
                # Clean up output file after sending
                if os.path.exists(output_filepath):
                    os.remove(output_filepath)
                    
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    return render_template('extract_mp3.html')

@app.route('/trim_video/<int:video_id>', methods=['GET', 'POST'])
def trim_video_view(video_id):
    """
    Render a page that lets the user select start and end times (in seconds)
    and optionally a new title. On POST, create a trimmed version using ffmpeg.
    """
    video = Video.query.get_or_404(video_id)
    preview = False
    trimmed_video_available = False
    error = None
    # Default new title to the current nickname
    new_title = video.nickname  

    if request.method == 'POST':
        try:
            start_time = float(request.form.get('start_time', 0))
            end_time = float(request.form.get('end_time', 0))
            new_title = request.form.get('new_title', video.nickname).strip() or video.nickname

            if start_time < 0 or end_time <= start_time:
                error = "Invalid start or end time. Please ensure end time is greater than start time."
            else:
                # Determine the file extension
                file_ext = os.path.splitext(video.stored_filepath)[1]
                # Create a temporary trimmed file path:
                trimmed_video_path = os.path.splitext(video.stored_filepath)[0] + "_trimmed" + file_ext

                # Use ffmpeg to trim the video (using -ss and -to with copy mode)
                (
                    ffmpeg
                    .input(video.stored_filepath, ss=start_time, to=end_time)
                    .output(trimmed_video_path, c='copy')
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                preview = True
                trimmed_video_available = True
        except Exception as e:
            error = f"Error during trimming: {str(e)}"

    return render_template(
        'trim_video.html',
        video=video,
        preview=preview,
        trimmed_video_available=trimmed_video_available,
        error=error,
        new_title=new_title
    )

@app.route('/accept_trim_video/<int:video_id>', methods=['POST'])
def accept_trim_video(video_id):
    """
    Replace the original video with the previously trimmed version.
    Optionally update the video title and regenerate the thumbnail.
    """
    video = Video.query.get_or_404(video_id)
    new_title = request.form.get('new_title', video.nickname).strip() or video.nickname
    file_ext = os.path.splitext(video.stored_filepath)[1]
    trimmed_video_path = os.path.splitext(video.stored_filepath)[0] + "_trimmed" + file_ext

    if not os.path.exists(trimmed_video_path):
        return jsonify({"error": "Trimmed video file not found."}), 404

    try:
        # Replace the original video with the trimmed version
        os.replace(trimmed_video_path, video.stored_filepath)
        
        # Update the video title if modified
        video.nickname = new_title
        
        # Regenerate a thumbnail based on the new trimmed video
        thumbnail_filename = f"thumbnail_{os.path.splitext(os.path.basename(video.stored_filepath))[0]}.jpg"
        thumbnails_dir = os.path.join(app.static_folder, 'thumbnails')
        os.makedirs(thumbnails_dir, exist_ok=True)
        thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)
        
        # Determine the video duration (to get a middle frame)
        probe = ffmpeg.probe(video.stored_filepath)
        duration = None
        for stream in probe['streams']:
            if 'duration' in stream:
                duration = float(stream['duration'])
                break
        if duration is None and 'format' in probe and 'duration' in probe['format']:
            duration = float(probe['format']['duration'])
        if duration is None:
            duration = 0
        
        (
            ffmpeg
            .input(video.stored_filepath, ss=duration/2 if duration > 0 else 0)
            .filter('scale', 320, -1)
            .output(thumbnail_path, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        relative_thumbnail_path = os.path.join('thumbnails', thumbnail_filename).replace('\\', '/')
        video.thumbnail_path = relative_thumbnail_path
        
        db.session.commit()
        return redirect(url_for('video.video_detail', video_id=video.id))
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/preview_trim_video/<int:video_id>')
def preview_trim_video(video_id):
    """
    Serve the trimmed video file so that it can be previewed.
    """
    video = Video.query.get_or_404(video_id)
    file_ext = os.path.splitext(video.stored_filepath)[1]
    trimmed_video_path = os.path.splitext(video.stored_filepath)[0] + "_trimmed" + file_ext
    if os.path.exists(trimmed_video_path):
        mimetype = 'video/mp4' if file_ext.lower() in ['.mp4'] else 'video/webm'
        return send_file(trimmed_video_path, mimetype=mimetype)
    else:
        return "Trimmed video not found", 404

@app.route('/tag/<tag>')
def tag_detail(tag):
    """Display a dedicated page for a specific tag with additional features."""
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'newest')
    per_page = 10

    # Create base queries for videos and tracks with this tag
    video_query = Video.query.filter(Video.tags.contains(tag))
    track_query = Track.query.filter(Track.tags.contains(tag))

    # Apply sorting
    if sort_by == 'newest':
        video_query = video_query.order_by(desc(Video.id))
        track_query = track_query.order_by(desc(Track.id))
    elif sort_by == 'oldest':
        video_query = video_query.order_by(Video.id)
        track_query = track_query.order_by(Track.id)
    elif sort_by == 'most_viewed':
        video_query = video_query.order_by(desc(Video.view_count))
        track_query = track_query.order_by(desc(Track.view_count))
    elif sort_by == 'most_liked':
        video_query = video_query.order_by(desc(Video.likes))
        track_query = track_query.order_by(desc(Track.likes))

    # Get all videos and tracks with this tag
    all_videos = video_query.all()
    all_tracks = track_query.all()
    
    # Combine and sort by creation time (using id as proxy)
    combined_content = []
    
    # Add videos with type indicator
    for video in all_videos:
        combined_content.append({
            'type': 'video',
            'id': video.id,
            'object': video,
            'sort_key': video.id
        })
    
    # Add tracks with type indicator
    for track in all_tracks:
        combined_content.append({
            'type': 'track',
            'id': track.id,
            'object': track,
            'sort_key': track.id
        })
    
    # Sort combined content by sort_key (id) in descending order for newest first
    if sort_by == 'newest':
        combined_content.sort(key=lambda x: x['sort_key'], reverse=True)
    elif sort_by == 'oldest':
        combined_content.sort(key=lambda x: x['sort_key'])
    elif sort_by == 'most_viewed':
        combined_content.sort(key=lambda x: x['object'].view_count or 0, reverse=True)
    elif sort_by == 'most_liked':
        combined_content.sort(key=lambda x: x['object'].likes or 0, reverse=True)
    
    # Manual pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_content = combined_content[start_idx:end_idx]
    
    # Calculate total pages
    total_items = len(combined_content)
    total_pages = (total_items + per_page - 1) // per_page
    
    # Get tag statistics (include both videos and tracks)
    video_count = len(all_videos)
    track_count = len(all_tracks)
    total_content_count = video_count + track_count
    
    total_views = sum((v.view_count or 0) for v in all_videos) + sum((t.view_count or 0) for t in all_tracks)
    total_likes = sum((v.likes or 0) for v in all_videos) + sum((t.likes or 0) for t in all_tracks)
    
    # Get related tags (tags that appear together with this tag)
    related_tags = []
    all_content_with_tag = all_videos + all_tracks
    tag_counts = {}
    
    for content in all_content_with_tag:
        if content.tags:
            content_tags = [t.strip() for t in content.tags.split(',')]
            for ctag in content_tags:
                if ctag.lower() != tag.lower() and ctag.strip():
                    tag_counts[ctag] = tag_counts.get(ctag, 0) + 1
    
    # Sort related tags by frequency and get top 10
    related_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Get tag description
    tag_description = TagDescription.query.filter_by(tag_name=tag).first()
    
    # Get tag comments
    tag_comments = TagComment.query.filter_by(tag_name=tag).order_by(TagComment.timestamp.desc()).all()
    
    return render_template(
        'tag_detail.html',
        tag=tag,
        content=paginated_content,
        all_content=combined_content,
        page=page,
        total_pages=total_pages,
        sort_by=sort_by,
        video_count=video_count,
        track_count=track_count,
        total_content_count=total_content_count,
        total_views=total_views,
        total_likes=total_likes,
        related_tags=related_tags,
        tag_description=tag_description,
        tag_comments=tag_comments
    )

@app.route('/edit_tag_description/<tag>', methods=['POST'])
def edit_tag_description(tag):
    description = request.form.get('description', '').strip()
    
    try:
        # Find existing tag description or create a new one
        tag_desc = TagDescription.query.filter_by(tag_name=tag).first()
        
        if tag_desc:
            tag_desc.description = description
            tag_desc.updated_at = datetime.utcnow()
        else:
            tag_desc = TagDescription(tag_name=tag, description=description)
            db.session.add(tag_desc)
            
        db.session.commit()
        return jsonify({"success": True, "description": description}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/add_tag_comment/<tag>', methods=['POST'])
def add_tag_comment(tag):
    author = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()
    
    if not author or not content:
        return jsonify({"error": "Name and comment are required"}), 400
    
    try:
        # Get or create artist for the comment author
        artist = get_or_create_artist_by_name(author)
        
        comment = TagComment(
            tag_name=tag,
            author=author,
            content=content,
            likes=0,
            author_artist_id=artist.id if artist else None
        )
        db.session.add(comment)
        db.session.commit()
        
        # Find avatar for this author
        author_slug = slugify_author(comment.author)
        profile = AuthorProfile.query.filter_by(slug=author_slug).first()
        avatar_rel = profile.avatar_path if profile and profile.avatar_path else None

        return jsonify({
            "success": True,
            "comment": {
                "id": comment.id,
                "author": comment.author,
                "author_slug": author_slug,
                "author_avatar": avatar_rel,
                "author_artist_id": artist.id if artist else None,
                "content": comment.content,
                "timestamp": comment.timestamp.strftime("%m/%d/%Y %I:%M %p"),
                "likes": comment.likes
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/like_tag_comment/<int:comment_id>', methods=['POST'])
def like_tag_comment(comment_id):
    comment = TagComment.query.get_or_404(comment_id)
    if comment.likes is None:
        comment.likes = 1
    else:
        comment.likes += 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": comment.likes})

@app.route('/delete_tag_comment/<int:comment_id>', methods=['POST'])
def delete_tag_comment(comment_id):
    comment = TagComment.query.get_or_404(comment_id)
    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/delete_playlist/<int:playlist_id>', methods=['POST'])
def delete_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    try:
        # Delete all playlist comments
        PlaylistComment.query.filter_by(playlist_id=playlist_id).delete()
        
        # Delete all playlist video associations
        PlaylistVideo.query.filter_by(playlist_id=playlist_id).delete()
        
        # Delete the playlist itself
        db.session.delete(playlist)
        db.session.commit()
        
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        ensure_directories_exist()
        db.create_all()
    app.run("0.0.0.0", 5015, debug=True)
