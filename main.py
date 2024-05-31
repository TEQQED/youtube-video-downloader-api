import asyncio
import io
import ssl
from uuid import uuid4
from quart import Quart, request, jsonify
from pytube import YouTube
import re
import os
from waitress import serve

from firebase import FIREBASE_CDN_URL, upload_file

app = Quart(__name__)

async def download_and_upload_video(url, resolution, path):
    byte_stream, error_message = await download_video(url, resolution)
    if byte_stream:
        await upload_file(byte_stream, path)
    
    if(error_message):
        print(error_message)

async def download_video(url, resolution):
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension='mp4', resolution=resolution).first()
        if stream:
            byte_stream = io.BytesIO()
            await asyncio.get_event_loop().run_in_executor(None, stream.stream_to_buffer, byte_stream)
            byte_stream.seek(0)  # Reset the stream position to the beginning
            return byte_stream, None
        else:
            return None, "Video with the specified resolution not found."
    except Exception as e:
        return None, str(e)

def get_video_info(url):
    try:
        yt = YouTube(url)
        video_info = {
            "title": yt.title,
            "author": yt.author,
            "length": yt.length,
            "views": yt.views,
            "description": yt.description,
            "publish_date": yt.publish_date
        }
        return video_info, None
    except Exception as e:
        return None, str(e)

def is_valid_youtube_url(url):
    pattern = r"^(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+(&\S*)?$"
    return re.match(pattern, url) is not None

@app.route('/download/<resolution>', methods=['POST'])
async def download_by_resolution(resolution):
    data = await request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400
    
    path = f'youtube-videos/{str(uuid4())}.mp4'
    
    asyncio.create_task(download_and_upload_video(url, resolution, path))
    
    return jsonify({"message": f"Video download started", "url": FIREBASE_CDN_URL(path)}), 200

@app.route('/video_info', methods=['POST'])
async def video_info():
    data = await request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400
    
    video_info, error_message = get_video_info(url)
    
    if video_info:
        return jsonify(video_info), 200
    else:
        return jsonify({"error": error_message}), 500

if __name__ == '__main__':
    if(os.environ.get('APP')):
        app.run(host="0.0.0.0", port=os.environ.get('PORT', 3001))
    else:
        ssl._create_default_https_context = ssl._create_unverified_context
        app.run(debug=True, port=8000)
