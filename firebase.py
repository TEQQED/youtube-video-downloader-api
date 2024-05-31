import asyncio
import base64
import io
import os
import firebase_admin
from firebase_admin import credentials, firestore, storage

# Path to your service account key file
def getCred(): 
  firebase_key_base64 = os.environ.get('FIREBASE_KEY_BASE64')
  if firebase_key_base64:
    firebase_key_json = base64.b64decode(firebase_key_base64)
    return credentials.Certificate(io.BytesIO(firebase_key_json))
  return credentials.Certificate('key.json')
  
  
firebase_admin.initialize_app(getCred(), {
    'storageBucket': 'sensorium-ec889.appspot.com'
})

# Firestore setup
db = firestore.client()

# Firebase Storage setup
bucket = storage.bucket()

def FIREBASE_CDN_URL(path):
    return f'https://firebasestorage.googleapis.com/v0/b/sensorium-ec889.appspot.com/o/{path}?alt=media&token=f7f0dbc1-941d-4dfc-9760-568f07b71f8e'

async def upload_file(byte_stream, path):
    bucket = storage.bucket()
    blob = bucket.blob(path)
    byte_stream.seek(0)
    blob.upload_from_file(byte_stream, content_type="video/mp4")