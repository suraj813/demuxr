import torch
import torchaudio
from ts.torch_handler.base_handler import BaseHandler
from pathlib import Path
import uuid
from loguru import logger
from diffq import DiffQuantizer
import io
import json
import boto3
import time
import numpy as np

# From https://github.com/facebookresearch/demucs/
from model import Demucs
from utils import load_model, apply_model

S3_CLIENT = boto3.client('s3')
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
torchaudio.utils.sox_utils.set_buffer_size(8192 * 2)


def read_ogg_from_s3(bucket, key):
    response = S3_CLIENT.get_object(Bucket=bucket, Key=key)
    waveform, sample_rate = torchaudio.load(response['Body'], format='ogg')
    return waveform

 
def read_model(model_weights_path):
    model = load_model(Demucs([1,1,1,1]), model_weights_path, True)
    return model



class DemucsHandler(BaseHandler):
    def __init__(self):
        self.model = None
        self.filedir = Path("filedir")
        self.filedir.mkdir(exist_ok=True)


    def initialize(self, ctx):
        """
        Initialize model. This will be called during model loading time
        :param context: Initial context contains model server system properties.
        :return:
        """
        self.manifest = ctx.manifest
        properties = ctx.system_properties
        model_weights_path = Path(properties.get("model_dir")) / Path(self.manifest['model']['serializedFile'])
        self.model = read_model(model_weights_path).to(DEVICE)


    def read_input(self, data):
        inp = data[0].get('data') or data[0].get('body') 
        s3_folder = (inp['Bucket'], inp['Key'].split('/')[0])
        wav = read_ogg_from_s3(inp['Bucket'], inp['Key'])
        wav = wav.to(DEVICE)
        return wav, s3_folder
        

    def preprocess(self, wav):
        """
        track: audio file
        :return: tensor of normalized audio
        """
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()
        logger.info(f"Processed audio into tensor of size {wav.size()}")
        return wav, ref


    def inference(self, wav, ref):
        if self.model is None:
            raise RuntimeError("Model not initialized")
        demuxed = apply_model(self.model, wav, 8)
        demuxed = demuxed * ref.std() + ref.mean()
        return demuxed


    # From https://github.com/facebookresearch/demucs/blob/dd7a77a0b2600d24168bbe7a40ef67f195586b62/demucs/separate.py#L207
    def postprocess(self, inference_output) -> Path:
        stems = []
        for source in inference_output:
            source = source / max(1.01 * source.abs().max(), 1)  # source.max(dim=1).values.max(dim=-1)
            source = (source * 2**15).clamp_(-2**15, 2**15 - 1).short()
            source = source.cpu().numpy()
            stems.append(source)
        return stems


    def cache(self, stems, s3_folder, fmt=None):
        bucket, folder = s3_folder
        key = folder + '/inferred.npz'
        source_names = ["drums", "bass", "other", "vocals"]
        stems = dict(zip(source_names, stems))
        with io.BytesIO() as buf_:
            np.savez_compressed(buf_, **stems)
            buf_.seek(0)
            S3_CLIENT.upload_fileobj(buf_, bucket, key)
        return key



    def handle(self, data, context):
        wav, s3_folder = self.read_input(data)

        tic = time.time()
        wav, ref = self.preprocess(wav)
        logger.info(f'preprocess took  {time.time()-tic}')
        
        tic = time.time()
        out = self.inference(wav, ref)
        logger.info(f'inference took  {time.time()-tic}')
        
        tic = time.time()
        stems = self.postprocess(out)        
        logger.info(f'postprocess took {time.time()-tic}')
    
        tic = time.time()
        key = self.cache(stems, s3_folder)
        logger.info(f'caching took {time.time()-tic}')

        result = {"bucket": s3_folder[0], "folder": s3_folder[1], "object": key}

        return [result]

