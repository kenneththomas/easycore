from flask import request, render_template, redirect, url_for
from . import filter_bp
from models import Video
from sqlalchemy import desc

@filter_bp.route('/filter')
def filter_videos():
    tag = request.args.get('tag')
    
    # If a tag is provided, redirect to the dedicated tag page
    if tag:
        return redirect(url_for('tag_detail', tag=tag))
    
    # Otherwise, continue with the existing filtering logic
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'newest')
    per_page = 10

    # Create base query
    query = Video.query

    # Apply sorting
    if sort_by == 'newest':
        query = query.order_by(desc(Video.id))
    elif sort_by == 'oldest':
        query = query.order_by(Video.id)
    elif sort_by == 'most_viewed':
        query = query.order_by(desc(Video.view_count))
    elif sort_by == 'most_liked':
        query = query.order_by(desc(Video.likes))

    paginated_videos = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('index.html', 
                         videos=paginated_videos.items, 
                         page=page, 
                         total_pages=paginated_videos.pages,
                         tag=tag,
                         sort_by=sort_by)







