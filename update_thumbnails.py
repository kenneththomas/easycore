import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import ffmpeg
from sqlalchemy import desc

# Ensure we're in the right directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Import your app configuration
sys.path.append(script_dir)
from vidtagger import app, Video, db

def generate_thumbnail(video_path, output_path):
    try:
        # Get video duration
        probe = ffmpeg.probe(video_path)
        duration = float(probe['streams'][0]['duration'])
        
        # Extract middle frame
        (
            ffmpeg
            .input(video_path, ss=duration/2)
            .filter('scale', 320, -1)
            .output(output_path, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return True
    except Exception as e:
        print(f"Error generating thumbnail for {video_path}: {str(e)}")
        return False

def update_thumbnails():
    with app.app_context():
        # Ensure the static/thumbnails directory exists
        thumbnails_dir = os.path.join(app.static_folder, 'thumbnails')
        os.makedirs(thumbnails_dir, exist_ok=True)

        videos = Video.query.filter(Video.thumbnail_path.is_(None)).all()
        total_videos = len(videos)
        print(f"Found {total_videos} videos without thumbnails.")

        for index, video in enumerate(videos, start=1):
            print(f"Processing video {index}/{total_videos}: {video.original_filepath}")
            
            if not os.path.exists(video.stored_filepath):
                print(f"Video file not found: {video.stored_filepath}")
                continue

            thumbnail_filename = f"thumbnail_{os.path.basename(video.stored_filepath).rsplit('.', 1)[0]}.jpg"
            thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)
            
            if generate_thumbnail(video.stored_filepath, thumbnail_path):
                # Update the thumbnail_path to be relative to the static folder
                # Use forward slashes for web paths
                relative_thumbnail_path = 'thumbnails/' + thumbnail_filename
                video.thumbnail_path = relative_thumbnail_path
                db.session.commit()
                print(f"Thumbnail generated and saved for video {video.id}")
            else:
                print(f"Failed to generate thumbnail for video {video.id}")

        print("Thumbnail update process completed.")

if __name__ == "__main__":
    update_thumbnails()