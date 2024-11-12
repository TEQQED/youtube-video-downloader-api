import asyncio
import io
import json
import ssl
from uuid import uuid4
from quart import Quart, request, jsonify
from pytubefix import YouTube
import re
import os
from quart_cors import cors
import http.client
from werkzeug.utils import secure_filename
from firebase import FIREBASE_CDN_URL, upload_file as upload_file_firebase, upload_downloaded_yt_file

max_content_mb = 200

app = Quart(__name__)
app = cors(app, allow_origin="*")
app.config['MAX_CONTENT_LENGTH'] = max_content_mb * 1024 * 1024 

async def download_and_upload_video(url, resolution, path):
    byte_stream, error_message = await download_video(url, resolution)
    if byte_stream:
        await upload_downloaded_yt_file(byte_stream, path)

    if(error_message):
        print(error_message)

async def download_video(url, resolution):
    try:
        # https://github.com/JuanBindez/pytubefix/issues/242
        stream = YouTube(url, client="IOS").streams.filter(
            progressive=False, subtype="mp4", resolution=resolution
        ).first()
        video_bytes = io.BytesIO()
        stream.stream_to_buffer(video_bytes)
        video_bytes.seek(0)
        return video_bytes, None
    except Exception as e:
        return None, str(e)

def get_video_info(url):
    url = url.replace("https://www.youtube.com/watch?v=", "")

    conn = http.client.HTTPSConnection("yt-api.p.rapidapi.com")

    headers = {
        'x-rapidapi-key': "891de1fb87mshebcc31864318d1cp1bbc0cjsne1a72cf06d70",
        'x-rapidapi-host': "yt-api.p.rapidapi.com"
    }


    conn.request("GET", f"/dl?id={url}", headers=headers)
    data = json.loads(conn.getresponse().read().decode("utf-8"))

    resolutions = ["720p", "480p", "360p", "240p", "144p"]
    available_resolutions = [stream['qualityLabel'] for stream in data['formats'] if 'qualityLabel' in stream]

    print(available_resolutions)

    selected_resolution = None
    for res in resolutions:
        if res in available_resolutions:
            print(res)
            selected_resolution = res
            break

    if not selected_resolution:
        return None, "No suitable resolution found."

    if(data['status'] != 'OK'):
        return None, data['message']
    return {
        'author': data['channelTitle'],
        'description': data['description'],
        'length': int(data['lengthSeconds']),
        'title': data['title'],
        'views': data['viewCount'],
        'thumbnail': data['thumbnail'][len(data['thumbnail']) -1]['url'],
        'resolution': selected_resolution
    }, None

@app.route('/upload', methods=['POST'])
async def upload_file():
    files = await request.files
    form = await request.form
    product_id = form.get('product_id')
    pid = f'___pid___{product_id}___pid___' if product_id else ''

    if 'file' not in files:
        return jsonify({"error": "No file part in the request."}), 400

    file = files.get("file")

    if not file.mimetype.startswith(('audio/', 'video/')):
        return jsonify({"error": "Uploaded file is not a music or video file."}), 400

    if file.content_length > 200 * 1024 * 1024:  # 200 MB
        return jsonify({"error": "File size exceeds the 200MB limit."}), 400

    if file.filename == '':
        return jsonify({"error": "No selected file."}), 400

    if file:
        filename = secure_filename(file.filename)
        byte_stream = file.read()

        path = f'user-uploaded-content/{pid}{uuid4()}-{filename}'
        if byte_stream:
            await upload_file_firebase(byte_stream, path)

        return jsonify({"message": "File successfully uploaded.", "file_path": FIREBASE_CDN_URL(path)}), 200
    else:
        return jsonify({"error": "File upload failed."}), 500


def is_valid_youtube_url(url):
    pattern = r"^(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+(&\S*)?$"
    return re.match(pattern, url) is not None

@app.route('/download/<resolution>', methods=['POST'])
async def download_by_resolution(resolution):
    data = await request.get_json()
    url = data.get('url')
    product_id = data.get('product_id')
    pid = f'___pid___{product_id}___pid___' if product_id else ''

    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400

    path = f'youtube-videos/{pid}{str(uuid4())}.mp4'

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
