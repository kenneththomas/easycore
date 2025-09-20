from flask import request, jsonify
from . import comment_bp
from models import db, Comment, PlaylistComment, TagComment, TrackComment

@comment_bp.route('/like_comment/<int:comment_id>', methods=['POST'])
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.likes is None:
        comment.likes = 1
    else:
        comment.likes += 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": comment.likes})

@comment_bp.route('/like_playlist_comment/<int:comment_id>', methods=['POST'])
def like_playlist_comment(comment_id):
    comment = PlaylistComment.query.get_or_404(comment_id)
    if comment.likes is None:
        comment.likes = 1
    else:
        comment.likes += 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": comment.likes})

@comment_bp.route('/like_tag_comment/<int:comment_id>', methods=['POST'])
def like_tag_comment(comment_id):
    comment = TagComment.query.get_or_404(comment_id)
    if comment.likes is None:
        comment.likes = 1
    else:
        comment.likes += 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": comment.likes})

@comment_bp.route('/like_track_comment/<int:comment_id>', methods=['POST'])
def like_track_comment(comment_id):
    comment = TrackComment.query.get_or_404(comment_id)
    if comment.likes is None:
        comment.likes = 1
    else:
        comment.likes += 1
    db.session.commit()
    return jsonify({"success": True, "new_like_count": comment.likes})







