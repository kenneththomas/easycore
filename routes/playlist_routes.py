from flask import Blueprint, jsonify, request
from models import db, Playlist, Video, Comment
from datetime import datetime

# Create blueprint
playlist_bp = Blueprint('playlist', __name__)

@playlist_bp.route('/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    try:
        comment = Comment.query.get_or_404(comment_id)
        db.session.delete(comment)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@playlist_bp.route('/like_comment/<int:comment_id>', methods=['POST'])
def like_comment(comment_id):
    try:
        comment = Comment.query.get_or_404(comment_id)
        comment.likes = (comment.likes or 0) + 1
        db.session.commit()
        return jsonify({'success': True, 'new_like_count': comment.likes})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@playlist_bp.route('/add_comment/<int:video_id>', methods=['POST'])
def add_comment(video_id):
    try:
        author = request.form.get('author')
        content = request.form.get('content')
        
        if not author or not content:
            return jsonify({'success': False, 'error': 'Author and content are required'})
        
        comment = Comment(
            video_id=video_id,
            author=author,
            content=content,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'author': comment.author,
                'content': comment.content,
                'timestamp': comment.timestamp.strftime("%m/%d/%Y %I:%M %p"),
                'likes': 0
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}) 