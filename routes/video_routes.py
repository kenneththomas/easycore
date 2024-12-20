from flask import request, jsonify, send_file, make_response, render_template
from . import video_bp
from models import db, Video
import os
import ffmpeg
from werkzeug.utils import secure_filename
from datetime import datetime
import random
import string
import re

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
        
        # ... rest of add_video implementation ...

@video_bp.route('/stream/<int:video_id>')
def stream_video(video_id):
    video = Video.query.get_or_404(video_id)
    # ... rest of stream_video implementation ...

@video_bp.route('/video/<int:video_id>')
def video_detail(video_id):
    video = Video.query.get_or_404(video_id)
    # ... rest of video_detail implementation ...

@video_bp.route('/delete/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    # ... rest of delete_video implementation ...

@video_bp.route('/edit_tags/<int:video_id>', methods=['POST'])
def edit_tags(video_id):
    video = Video.query.get_or_404(video_id)
    # ... rest of edit_tags implementation ...

@video_bp.route('/edit_description/<int:video_id>', methods=['POST'])
def edit_description(video_id):
    video = Video.query.get_or_404(video_id)
    # ... rest of edit_description implementation ...

@video_bp.route('/edit_title/<int:video_id>', methods=['POST'])
def edit_title(video_id):
    video = Video.query.get_or_404(video_id)
    # ... rest of edit_title implementation ...

@video_bp.route('/move_to_regular/<int:video_id>', methods=['POST'])
def move_to_regular(video_id):
    video = Video.query.get_or_404(video_id)
    # ... rest of move_to_regular implementation ...

@video_bp.route('/like/<int:video_id>', methods=['POST'])
def like_video(video_id):
    video = Video.query.get_or_404(video_id)
    # ... rest of like_video implementation ...

@video_bp.route('/increment_view/<int:video_id>', methods=['POST'])
def increment_view(video_id):
    video = Video.query.get_or_404(video_id)
    # ... rest of increment_view implementation ...

@video_bp.route('/bulk_upload', methods=['GET', 'POST'])
def bulk_upload():
    # ... bulk_upload implementation ...

@video_bp.route('/cleanup_stealth', methods=['POST'])
def cleanup_stealth():
    # ... cleanup_stealth implementation ... 