from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, Response, make_response
from flask_sqlalchemy import SQLAlchemy
import os
from sqlalchemy import desc, func
import re
from werkzeug.utils import secure_filename
import ffmpeg
from PIL import Image
import io

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///videos.db'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
app.config['STEALTH_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'stealth_uploads')
db = SQLAlchemy(app)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filepath = db.Column(db.String(255), nullable=False)
    stored_filepath = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(100))
    description = db.Column(db.Text)
    tags = db.Column(db.String(255))
    thumbnail_path = db.Column(db.String(255))  # New field for thumbnail

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    videos = Video.query.order_by(desc(Video.id)).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('index.html', videos=videos.items, page=page, total_pages=videos.pages, tag=None)

@app.route('/add', methods=['GET', 'POST'])
def add_video():
    if request.method == 'POST':
        file = request.files.get('file')
        nickname = request.form.get('nickname')
        description = request.form.get('description')
        tags = request.form.get('tags')
        stealth = request.form.get('stealth') == 'on'
        
        if not file:
            return jsonify({"error": "No file provided"}), 400
        
        original_filepath = file.filename
        original_extension = os.path.splitext(original_filepath)[1]
        
        if nickname:
            new_filename = secure_filename(nickname + original_extension)
        else:
            new_filename = secure_filename(original_filepath)
        
        if stealth:
            stored_filepath = os.path.join(app.config['STEALTH_UPLOAD_FOLDER'], new_filename)
            upload_folder = app.config['STEALTH_UPLOAD_FOLDER']
        else:
            stored_filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            upload_folder = app.config['UPLOAD_FOLDER']
        
        try:
            os.makedirs(upload_folder, exist_ok=True)
            file.save(stored_filepath)
            
            # Generate thumbnail
            thumbnail_filename = f"thumbnail_{os.path.splitext(new_filename)[0]}.jpg"
            thumbnails_dir = os.path.join(app.static_folder, 'thumbnails')
            os.makedirs(thumbnails_dir, exist_ok=True)
            thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)
            
            # Get video duration
            probe = ffmpeg.probe(stored_filepath)
            duration = float(probe['streams'][0]['duration'])
            
            # Extract middle frame
            (
                ffmpeg
                .input(stored_filepath, ss=duration/2)
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
                              thumbnail_path=relative_thumbnail_path)
            db.session.add(new_video)
            db.session.commit()
            
            return jsonify({"success": True, "video_id": new_video.id}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
    
    # Get existing tags for GET request
    tags = db.session.query(
        func.trim(func.lower(func.substr(Video.tags, 1, func.instr(Video.tags + ',', ',') - 1))).cast(db.String).label('tag'),
        func.count('*').label('count')
    ).group_by('tag').order_by(desc('count')).all()
    
    return render_template('add.html', existing_tags=tags)

@app.route('/stream/<int:video_id>')
def stream_video(video_id):
    video = Video.query.get_or_404(video_id)
    
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
        resp.headers.set('Content-Type', 'video/mp4')
        resp.headers.set('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        resp.headers.set('Accept-Ranges', 'bytes')
        resp.headers.set('Content-Length', str(length))
        return resp, 206
    else:
        return send_file(video.stored_filepath, mimetype='video/mp4')

@app.route('/filter')
def filter_videos():
    tag = request.args.get('tag')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    if tag:
        videos = Video.query.filter(Video.tags.contains(tag)).order_by(desc(Video.id))
    else:
        videos = Video.query.order_by(desc(Video.id))

    paginated_videos = videos.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('index.html', 
                           videos=paginated_videos.items, 
                           page=page, 
                           total_pages=paginated_videos.pages,
                           tag=tag)

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

@app.route('/video/<int:video_id>')
def video_detail(video_id):
    video = Video.query.get_or_404(video_id)
    return render_template('video_detail.html', video=video)

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
    
    matching_tags = [tag[0] for tag in all_tags if query in tag[0].lower()]
    matching_tags.sort(key=lambda x: x.lower().index(query))  # Sort by relevance
    return jsonify(matching_tags[:10])  # Return top 10 matches

@app.route('/thumbnail/<int:video_id>')
def serve_thumbnail(video_id):
    video = Video.query.get_or_404(video_id)
    thumbnail_path = os.path.join(app.static_folder, video.thumbnail_path)
    return send_file(thumbnail_path, mimetype='image/jpeg')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run("0.0.0.0", 5015, debug=True)