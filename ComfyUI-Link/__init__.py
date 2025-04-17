from .nodes import ComfyLinkSaveImage, ComfyLinkVSHResult, ComfyLinkLoadImage, ComfyLinkLoadAudio, ComfyLinkSaveAudio

# 注册节点
NODE_CLASS_MAPPINGS = {
    "ComfyLink:SaveImage": ComfyLinkSaveImage,
    "ComfyLink:VSHResult": ComfyLinkVSHResult,
    "ComfyLink:LoadImage": ComfyLinkLoadImage,
    "ComfyLink:LoadAudio": ComfyLinkLoadAudio,
    "ComfyLink:SaveAudio": ComfyLinkSaveAudio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
  "ComfyLink:SaveImage": "ComfyLink: SaveImage",
  "ComfyLink:VSHResult": "ComfyLink: VSHResult",
  "ComfyLink:LoadImage": "ComfyLink: LoadImage",
  "ComfyLink:LoadAudio": "ComfyLink: LoadAudio",
  "ComfyLink:SaveAudio": "ComfyLink: SaveAudio",
}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
