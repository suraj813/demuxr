from flask import Flask, request
import requests
from flask_cors import CORS, cross_origin
import youtube_dl
from pathlib import Path
import tempfile
from loguru import logger
import s3_helper as s3
import io
import json
import time
import boto3
from botocore.config import Config

app = Flask(__name__)
cors = CORS(app)
torchserve_url = "http://model:8080/"
pred_endpoint = "predictions/demucs_quantized/1"
BUCKET = "demucs-app-cache"

lambda_client = boto3.client('lambda', region_name='us-east-1', config=Config(read_timeout=180))


def get_yt_audio(url):
    """
    downloads the url
    returns path of the audio
    TODO: return fileobj instead and delete tmp file
    """
    with tempfile.TemporaryDirectory() as temp:
        ydl_opts = {
            'quiet':True,
            'outtmpl':f'{temp}/%(id)s/original.%(ext)s',
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'vorbis',
                'preferredquality': '128',}],
                'postprocessor_args': ['-ar', '44100'],
        }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
    audio_path = Path(temp) / info_dict['id'] / 'original.ogg'
    return audio_path

# movable to frontend/js
def get_yt_metadata(url):
    """
        response = {
        'url': url,
        'title': info_dict['title'],
        'id': info_dict['id'],
        # 'folder': s3.get_url(info_dict['id']),
        # 'status': 200
    }"""
    metadata = {}
    with youtube_dl.YoutubeDL({}) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        metadata['url'] = url
        metadata['title'] = info_dict.get('title', '')
        metadata['video_id'] = info_dict.get('id')
        metadata['s3_url'] = s3.get_url(info_dict.get('id'))
    return metadata

# movable to frontend/js
def run_inference(key):
    """ship audio to model"""
    resp = requests.post(url="http://model:8080/predictions/demucs_quantized/1", json={'Bucket': BUCKET, 'Key': key})
    if resp.status_code != 200:
        raise RuntimeError(f"Torchserve inference failed with HTTP {resp.status_code} | {resp.text}")


def run_encode(inferred_loc):
    """
    aws --debug --cli-read-timeout 0  lambda invoke --function-name test --payload '{"bucket": "demucs-app-cache", "object": "test/inferred.npz"}' out.json
    """
    logger.info("Invoking encode function on Lambda")
    ret  = lambda_client.invoke(FunctionName='test', InvocationType='RequestResponse', Payload=json.dumps(inferred_loc))
    return ret


@app.route("/api/info")
@cross_origin()
def info():
    url = request.args.get('url')
    return get_yt_metadata(url)

@app.route("/api/demux")
@cross_origin()
def demux():
    url = request.args.get('url')
    folder = request.args.get('folder')
    logger.info(f"Received request of url {url} and folder {folder}")

    is_input_cached = lambda folder: s3.grep(folder + '/original.ogg')
    is_inferred = lambda folder: s3.grep(folder + '/inferred.npz')
    is_encoded = lambda folder: s3.grep(folder + '/vocals.ogg')
    
    if is_encoded(folder):
       return {'response': s3.get_url(folder), 'status': 200}

    if is_inferred(folder):
        inferred_loc = {"bucket": BUCKET, "object": f"{folder}/inferred.npz"}
        encoded = run_encode(inferred_loc)
    
    elif is_input_cached(folder):
        key = f'{folder}/original.ogg'
        run_inference(key)
        inferred_loc = {"bucket": BUCKET, "object": f"{folder}/inferred.npz"}
        encoded = run_encode(inferred_loc)
    
    else:
        audio_path = get_yt_audio(url)
        s3.upload_stem(audio_path) 
        key = f'{folder}/original.ogg'
        run_inference(key)
        inferred_loc = {"bucket": BUCKET, "object": f"{folder}/inferred.npz"}
        encoded = run_encode(inferred_loc)
    
    resp = {'response': s3.get_url(folder), 'status': encoded['StatusCode']}
    logger.info(resp)
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)