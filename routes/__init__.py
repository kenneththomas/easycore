from flask import Blueprint

# Create blueprints
video_bp = Blueprint('video', __name__)
playlist_bp = Blueprint('playlist', __name__)
comment_bp = Blueprint('comment', __name__)
filter_bp = Blueprint('filter', __name__)

# Import routes
from . import video_routes
from . import playlist_routes
from . import comment_routes
from . import filter_routes
