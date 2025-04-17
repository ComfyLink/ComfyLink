import os
import torch
import torchaudio
import numpy as np
import requests
from io import BytesIO
import json
import node_helpers
from PIL import Image, ImageOps, ImageSequence
from .utils import is_url, strip_path, try_download_video, get_audio, validate_path, hash_path

class ComfyLinkSaveImage:
  """保存图片并上传到指定地址的节点"""
  def __init__(self):
    self.token = ""
    self.compress_level = 7
  
  @classmethod
  def INPUT_TYPES(cls):
    return {
      "required": {
        "images": ("IMAGE",),  # ComfyUI 图片输入
        "task_id": ("STRING", {
          "default": '{COMFYLINK:TASK_ID}',
          "multiline": False
        }),
      },
      "optional": {
        "url": ("STRING", {
          "default": 'https://api.comfylink.com/v1/report/%s/result',
          "multiline": False
        }),
        "uid": ("STRING", {
          "default": '',
          "multiline": False
        }),
        "node_id": ("STRING", {
          "default": '0',
          "multiline": False
        }),
      }
    }

  RETURN_TYPES = ()
  FUNCTION = "save_and_upload"
  OUTPUT_NODE = True
  CATEGORY = "Image"  # 修改分类名称

  def save_and_upload(self, images, task_id, url="https://api.comfylink.com/v1/report/%s/result", uid="", node_id="0"):

    headers = {
      "X-User-ID": uid
    }
    result = []

    for idx, image in enumerate(images):
      # 将 tensor 转换为 PIL Image
      i = 255. * image.cpu().numpy()
      img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
      filename = f'{idx:04d}.png'
      # 转换为更节省空间的格式（WebP）
      buffer = BytesIO()
      img.save(buffer, format="png", optimize=True, compress_level=self.compress_level)
      image_data = buffer.getvalue()
        
      try:
        # 上传图片
        files = {'file': (filename, image_data, 'image/png')}
        
        response = requests.post(url % task_id,
          files=files,
          headers=headers,
          data={
            "task_id": task_id,
          }
        )
        
        if response.status_code == 200:
          data = response.json()
          if data["code"] == 0:
            result.append(data["data"]["url"])
          else:
            raise Exception(f"图片上传失败: {data.msg}")
        else:
          raise Exception(f"图片上传失败: {response.status_code}")
              
      except Exception as e:
        raise Exception(f"上传过程中出错: {str(e)}")
    result_json = json.dumps({"result": result, "node_id": node_id})
    return {"ui": {"text": [result_json]}}

class ComfyLinkVSHResult:
  """获取任务结果的节点"""
  @classmethod
  def INPUT_TYPES(cls):
    return {
      "required": {
        "filesnames": ("VHS_FILENAMES",),  # VideoHelperSuite 文件名输入
        "task_id": ("STRING", {
          "default": '{COMFYLINK:TASK_ID}',
          "multiline": False
        }),
      },
      "optional": {
        "url": ("STRING", {
          "default": 'https://api.comfylink.com/v1/report/%s/result',
          "multiline": False
        }),
        "uid": ("STRING", {
          "default": '',
          "multiline": False
        }),
        "node_id": ("STRING", {
          "default": 'video',
          "multiline": False
        }),
      }
    }

  RETURN_TYPES = ()
  FUNCTION = "get_result"
  OUTPUT_NODE = True
  CATEGORY = "VideoHelperSuite"  # 修改分类名称

  def get_result(self, filesnames, task_id, url="https://api.comfylink.com/v1/report/%s/result", uid="", node_id="0"):
    files = filesnames[1]
    headers = {
      "X-User-ID": uid
    }
    result = []
    for file in files:
      try:
        # 读取文件并上传
        with open(file, 'rb') as f:
          files = {'file': f}
          response = requests.post(
            url % task_id,
            files=files,
            headers=headers
          )
          
          if response.status_code == 200:
            data = response.json()
            if data["code"] == 0:
              result.append(data["data"]["url"])
              print(f"文件 {file} 上传成功")
            else:
              raise Exception(f"文件上传失败: {data.msg}")
          else:
            raise Exception(f"文件上传失败: {response.status_code}")
              
      except Exception as e:
        print(f"上传文件 {file} 出错: {str(e)}")
    result_json = json.dumps({"result": result, "node_id": node_id})
    return {"ui": {"text": [result_json]}}

def load_image(url, timeout=10):
  # Load the image from the URL
  response = requests.get(url, timeout=timeout)

  content_type = response.headers.get('Content-Type')
  return Image.open(BytesIO(response.content))

class ComfyLinkLoadImage:
  """加载图片"""
  @classmethod
  def INPUT_TYPES(s):
    return {"required":
      {"image": ("STRING", {"default": ""})},
    }

  CATEGORY = "image"

  RETURN_TYPES = ("IMAGE", "MASK")
  FUNCTION = "load_image"
  def load_image(self, image):
    if image.startswith("http"):
      img = load_image(image)
    else:
      img = Image.open(image)
    output_images = []
    output_masks = []
    w, h = None, None
    for i in ImageSequence.Iterator(img):
      i = node_helpers.pillow(ImageOps.exif_transpose, i)
      if i.mode == 'I':
        i = i.point(lambda i: i * (1 / 255))
      image = i.convert("RGB")

      if len(output_images) == 0:
        w = image.size[0]
        h = image.size[1]
      
      if image.size[0] != w or image.size[1] != h:
        continue
      
      image = np.array(image).astype(np.float32) / 255.0
      image = torch.from_numpy(image)[None,]

      if 'A' in i.getbands():
        mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
        mask = 1. - torch.from_numpy(mask)
      else:
        mask = torch.zeros((64,64), dtype=torch.float32, device="cpu")
      
      output_images.append(image)
      output_masks.append(mask.unsqueeze(0))
    
    if len(output_images) > 1 and img.format not in excluded_formats:
      output_image = torch.cat(output_images, dim=0)
      output_mask = torch.cat(output_masks, dim=0)
    else:
      output_image = output_images[0]
      output_mask = output_masks[0]

    return (output_image, output_mask)

  @classmethod
  def IS_CHANGED(s, image):
    return image

class ComfyLinkLoadAudio:
  """加载音频"""
  @classmethod
  def INPUT_TYPES(s):
    return {"required":
      {
        "audio": ("STRING", {"default": ""}),
        "start_time": ("FLOAT" , {"default": 0, "min": 0, "max": 10000000, "step": 0.01}),
        "duration": ("FLOAT" , {"default": 0, "min": 0, "max": 10000000, "step": 0.01}),
      },
    }
  CATEGORY = "audio"
  RETURN_TYPES = ("AUDIO",)
  FUNCTION = "load_audio"
  def load_audio(self, audio, start_time, duration):
    audio_file = strip_path(audio)
    if is_url(audio_file):
      audio_file = try_download_video(audio_file)
    return (get_audio(audio_file, start_time=start_time, duration=duration),)
  
  @classmethod
  def IS_CHANGED(s, audio, start_time, duration):
    return hash_path(audio)

  @classmethod
  def VALIDATE_INPUTS(s, audio_file, **kwargs):
    return validate_path(audio, allow_none=True)

class ComfyLinkSaveAudio:
  """保存音频并上传到指定地址的节点"""
  def __init__(self):
    self.token = ""
  
  @classmethod
  def INPUT_TYPES(cls):
    return {
      "required": {
        "audio": ("AUDIO", ),  # ComfyUI 音频输入
        "task_id": ("STRING", {
          "default": '{COMFYLINK:TASK_ID}',
          "multiline": False
        }),
      },
      "optional": {
        "url": ("STRING", {
          "default": 'https://api.comfylink.com/v1/report/%s/result',
          "multiline": False
        }),
        "uid": ("STRING", {
          "default": '',
          "multiline": False
        }),
        "node_id": ("STRING", {
          "default": '0',
          "multiline": False
        }),
      }
    }

  RETURN_TYPES = ()
  FUNCTION = "save_and_upload"
  OUTPUT_NODE = True
  CATEGORY = "audio"  # 修改分类名称

  def save_and_upload(self, audio, task_id, url="https://api.comfylink.com/v1/report/%s/result", uid="", node_id="0"):

    headers = {
      "X-User-ID": uid
    }
    result = []

    for (batch_number, waveform) in enumerate(audio["waveform"].cpu()):
      file = f"comfylink_audio_{batch_number:04d}.wav"
      buffer = BytesIO()
      torchaudio.save(buffer, waveform, audio["sample_rate"])
      audio_data = buffer.getvalue()
        
      try:
        # 上传图片
        files = {'file': (file, audio_data, 'audio/x-wav')}
        
        response = requests.post(url % task_id,
          files=files,
          headers=headers,
          data={
            "task_id": task_id,
          }
        )
        
        if response.status_code == 200:
          data = response.json()
          if data["code"] == 0:
            result.append(data["data"]["url"])
          else:
            raise Exception(f"音频上传失败: {data.msg}")
        else:
          raise Exception(f"音频上传失败: {response.status_code}")
              
      except Exception as e:
        raise Exception(f"上传过程中出错: {str(e)}")
    result_json = json.dumps({"result": result, "node_id": node_id})
    return {"ui": {"text": [result_json]}}