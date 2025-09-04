from flask import request, jsonify, send_file, make_response, render_template, current_app
from . import video_bp
from models import db, Video, Comment, AuthorProfile
from sqlalchemy import desc
import os
import ffmpeg
from werkzeug.utils import secure_filename
from datetime import datetime
import random
import string
import re
import unicodedata

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

@video_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'newest')
    per_page = 10

    query = Video.query

    if sort_by == 'newest':
        query = query.order_by(desc(Video.id))
    elif sort_by == 'oldest':
        query = query.order_by(Video.id)
    elif sort_by == 'most_viewed':
        query = query.order_by(desc(Video.view_count))
    elif sort_by == 'most_liked':
        query = query.order_by(desc(Video.likes))

    videos = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('index.html', 
                         videos=videos.items, 
                         page=page, 
                         total_pages=videos.pages, 
                         tag=None,
                         sort_by=sort_by)

@video_bp.route('/add', methods=['GET', 'POST'])
def add_video():
    if request.method == 'POST':
        file = request.files.get('file')
        nickname = request.form.get('nickname')
        description = request.form.get('description')
        tags = request.form.get('tags')
        stealth = request.form.get('stealth') == 'on'
        
        if not nickname and tags:
            nickname = ' '.join(tag.strip() for tag in tags.split(','))
        
        if not file:
            return jsonify({"error": "No file provided"}), 400
        
        original_filepath = file.filename
        original_extension = os.path.splitext(original_filepath)[1]
        
        if nickname:
            base_filename = secure_filename(nickname + original_extension)
        else:
            base_filename = secure_filename(original_filepath)
        
        # Get upload folder from app config
        upload_folder = current_app.config['STEALTH_UPLOAD_FOLDER'] if stealth else current_app.config['UPLOAD_FOLDER']
        new_filename, stored_filepath = generate_unique_filename(base_filename, upload_folder)
        
        try:
            os.makedirs(upload_folder, exist_ok=True)
            file.save(stored_filepath)
            
            # Convert WebM to MP4 if necessary
            if original_extension == '.webm':
                stored_filepath = convert_webm_to_mp4(stored_filepath)
                new_filename = os.path.basename(stored_filepath)
            
            # Generate thumbnail
            thumbnail_filename = f"thumbnail_{os.path.splitext(new_filename)[0]}.jpg"
            thumbnails_dir = os.path.join(current_app.static_folder, 'thumbnails')
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
            
            new_video = Video(original_filepath=original_filepath, 
                              stored_filepath=stored_filepath,
                              nickname=nickname, 
                              description=description, 
                              tags=tags,
                              thumbnail_path=relative_thumbnail_path,
                              view_count=0)  # Initialize view_count to 0
            db.session.add(new_video)
            db.session.commit()
            
            return jsonify({"success": True, "video_id": new_video.id}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
    
    # Replace the existing tags query with a query for recent tags
    recent_tags = db.session.query(
        Video.tags, Video.id
    ).order_by(
        desc(Video.id)  # Order by most recent videos first
    ).limit(20).all()  # Get tags from last 20 videos
    
    # Process the tags to get unique recent tags
    processed_tags = []
    seen_tags = set()
    
    for video_tags, _ in recent_tags:
        if video_tags:  # Check if tags exist
            tags_list = [tag.strip() for tag in video_tags.split(',')]
            for tag in tags_list:
                if tag and tag.lower() not in seen_tags:  # Avoid duplicates
                    seen_tags.add(tag.lower())
                    processed_tags.append(tag)
    
    return render_template('add.html', recent_tags=processed_tags[:20])

@video_bp.route('/video/<int:video_id>')
def video_detail(video_id):
    video = Video.query.get_or_404(video_id)
    if video.view_count is None:
        video.view_count = 1
    else:
        video.view_count += 1
    
    related_videos = get_related_videos(video)
    comments = Comment.query.filter_by(video_id=video_id).order_by(Comment.timestamp.desc()).all()
    # Build author avatar mapping for template
    author_slugs = {slugify_author(c.author) for c in comments}
    avatars = {}
    if author_slugs:
        profiles = AuthorProfile.query.filter(AuthorProfile.slug.in_(author_slugs)).all()
        for p in profiles:
            if p.avatar_path:
                avatars[p.slug] = p.avatar_path
    db.session.commit()
    return render_template('video_detail.html', video=video, related_videos=related_videos, comments=comments, author_avatars=avatars) 