"""
Comfyui_o1key Plugin
Nano Banana image generation integration for ComfyUI
"""
from .nodes import (
    NanoBananaTextToImage,
    NanoBananaImageToImage,
    NanoBananaBatchProcessor,
    NanoBananaAPIConfig,
)

# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "NanoBananaTextToImage": NanoBananaTextToImage,
    "NanoBananaImageToImage": NanoBananaImageToImage,
    "NanoBananaBatchProcessor": NanoBananaBatchProcessor,
    "NanoBananaAPIConfig": NanoBananaAPIConfig,
}

# Node display names in ComfyUI interface
NODE_DISPLAY_NAME_MAPPINGS = {
    "NanoBananaTextToImage": "Nano Banana 文生图",
    "NanoBananaImageToImage": "Nano Banana 图生图",
    "NanoBananaBatchProcessor": "Nano Banana 批量处理",
    "NanoBananaAPIConfig": "Nano Banana API配置",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
__version__ = "1.3.0"

# Print initialization message
print("🍌 Comfyui_o1key v1.3.0 加载成功!")
print("   - Nano Banana 文生图")
print("   - Nano Banana 图生图")
print("   - Nano Banana 批量处理")
print("   - Nano Banana API配置")
print("   - Powered by o1key.com")
