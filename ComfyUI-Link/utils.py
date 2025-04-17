import hashlib
import os
import shutil
import subprocess
import datetime
import folder_paths
import torch
import re

ENCODE_ARGS = ("utf-8", 'backslashreplace')
download_history = {}


def try_download_video(url, timeout=60):
  # 使用aria2c下载视频文件
  output_name = download_history[url]
  if url in download_history:
    output_name = download_history[url]
    if os.path.exists(output_name):
      return output_name
  
  filename = os.path.basename(url)
  # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
  # url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
  # url_ext = os.path.splitext(url)[1]
  # if not url_ext:
    # url_ext = ".mp4"
  temp_dir = os.path.join(folder_paths.get_temp_directory(), "inputs")
  os.makedirs(temp_dir, exist_ok=True)
  output_filename = os.path.join(temp_dir, f"video_{filename}")
  try:
    # 检查aria2c是否可用
    aria2c_path = shutil.which("aria2c")
    if aria2c_path is None:
      # 如果aria2c不可用，回退到requests
      response = requests.get(url, timeout=timeout)
      with open(output_filename, 'wb') as f:
        f.write(response.content)
    else:
      # 使用aria2c下载视频文件
      # 使用aria2c下载文件
      cmd = [
        aria2c_path,
        "--max-connection-per-server=16",  # 每个服务器最大连接数
        "--min-split-size=1M",             # 最小分片大小
        "--split=16",                      # 分片数
        "--max-concurrent-downloads=16",   # 最大并发下载数
        "--connect-timeout=10",            # 连接超时
        f"--timeout={timeout}",            # 超时时间
        "--auto-file-renaming=false",      # 禁止自动重命名
        "--allow-overwrite=true",          # 允许覆盖
        "-d", temp_dir,                    # 下载目录
        "-o", os.path.basename(output_filename),  # 输出文件名
        url                                # 下载URL
      ]
      result = subprocess.run(cmd, capture_output=True, text=True)
      if result.returncode != 0:
        # 如果aria2c下载失败，回退到requests
        response = requests.get(url, timeout=timeout)
        with open(output_filename, 'wb') as f:
          f.write(response.content)
  except Exception as e:
    print(f"Failed to download video file: {e}")
    # 如果下载失败，回退到requests
    response = requests.get(url, timeout=timeout)
    with open(output_filename, 'wb') as f:
      f.write(response.content)
  download_history[url] = output_filename
  return output_filename

# 引用自https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/blob/main/videohelpersuite/utils.py

def ffmpeg_suitability(path):
  try:
    version = subprocess.run([path, "-version"], check=True,
                            capture_output=True).stdout.decode(*ENCODE_ARGS)
  except:
    return 0
  score = 0
  #rough layout of the importance of various features
  simple_criterion = [("libvpx", 20),("264",10), ("265",3),
                      ("svtav1",5),("libopus", 1)]
  for criterion in simple_criterion:
    if version.find(criterion[0]) >= 0:
      score += criterion[1]
  #obtain rough compile year from copyright information
  copyright_index = version.find('2000-2')
  if copyright_index >= 0:
    copyright_year = version[copyright_index+6:copyright_index+9]
    if copyright_year.isnumeric():
      score += int(copyright_year)
  return score

if "VHS_FORCE_FFMPEG_PATH" in os.environ:
  ffmpeg_path = os.environ.get("VHS_FORCE_FFMPEG_PATH")
else:
  ffmpeg_paths = []
  try:
    from imageio_ffmpeg import get_ffmpeg_exe
    imageio_ffmpeg_path = get_ffmpeg_exe()
    ffmpeg_paths.append(imageio_ffmpeg_path)
  except:
    if "VHS_USE_IMAGEIO_FFMPEG" in os.environ:
      raise
    logger.warn("Failed to import imageio_ffmpeg")
  if "VHS_USE_IMAGEIO_FFMPEG" in os.environ:
    ffmpeg_path = imageio_ffmpeg_path
  else:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg is not None:
      ffmpeg_paths.append(system_ffmpeg)
    if os.path.isfile("ffmpeg"):
      ffmpeg_paths.append(os.path.abspath("ffmpeg"))
    if os.path.isfile("ffmpeg.exe"):
      ffmpeg_paths.append(os.path.abspath("ffmpeg.exe"))
    if len(ffmpeg_paths) == 0:
      logger.error("No valid ffmpeg found.")
      ffmpeg_path = None
    elif len(ffmpeg_paths) == 1:
      #Evaluation of suitability isn't required, can take sole option
      #to reduce startup time
      ffmpeg_path = ffmpeg_paths[0]
    else:
      ffmpeg_path = max(ffmpeg_paths, key=ffmpeg_suitability)
# 引用自https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/blob/main/videohelpersuite/utils.py
def is_url(url):
   return url.split("://")[0] in ["http", "https"]

# modified from https://stackoverflow.com/questions/22058048/hashing-a-file-in-python
def calculate_file_hash(filename: str, hash_every_n: int = 1):
  #Larger video files were taking >.5 seconds to hash even when cached,
  #so instead the modified time from the filesystem is used as a hash
  h = hashlib.sha256()
  h.update(filename.encode())
  h.update(str(os.path.getmtime(filename)).encode())
  return h.hexdigest()

def strip_path(path):
  #This leaves whitespace inside quotes and only a single "
  #thus ' ""test"' -> '"test'
  #consider path.strip(string.whitespace+"\"")
  #or weightier re.fullmatch("[\\s\"]*(.+?)[\\s\"]*", path).group(1)
  path = path.strip()
  if path.startswith("\""):
    path = path[1:]
  if path.endswith("\""):
    path = path[:-1]
  return path

def hash_path(path):
  if path is None:
    return "input"
  if is_url(path):
    return "url"
  return calculate_file_hash(strip_path(path))

# 引用自 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/blob/main/videohelpersuite/utils.py
def get_audio(file, start_time=0, duration=0):
  args = [ffmpeg_path, "-i", file]
  if start_time > 0:
    args += ["-ss", str(start_time)]
  if duration > 0:
    args += ["-t", str(duration)]
  try:
    #TODO: scan for sample rate and maintain
    res =  subprocess.run(args + ["-f", "f32le", "-"],
                          capture_output=True, check=True)
    audio = torch.frombuffer(bytearray(res.stdout), dtype=torch.float32)
    match = re.search(', (\\d+) Hz, (\\w+), ',res.stderr.decode(*ENCODE_ARGS))
  except subprocess.CalledProcessError as e:
    raise Exception(f"VHS failed to extract audio from {file}:\n" \
              + e.stderr.decode(*ENCODE_ARGS))
  if match:
    ar = int(match.group(1))
    #NOTE: Just throwing an error for other channel types right now
    #Will deal with issues if they come
    ac = {"mono": 1, "stereo": 2}[match.group(2)]
  else:
    ar = 44100
    ac = 2
  audio = audio.reshape((-1,ac)).transpose(0,1).unsqueeze(0)
  return {'waveform': audio, 'sample_rate': ar}

# 引用自https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/blob/main/videohelpersuite/utils.py
def validate_path(path, allow_none=False, allow_url=True):
  if path is None:
    return allow_none
  if is_url(path):
    #Probably not feasible to check if url resolves here
    if not allow_url:
      return "URLs are unsupported for this path"
    return True
  if not os.path.isfile(strip_path(path)):
    return "Invalid file path: {}".format(path)
  return True