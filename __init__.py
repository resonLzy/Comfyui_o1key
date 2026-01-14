"""
Comfyui_o1key Plugin
Nano Banana image generation integration for ComfyUI
"""
from .nodes import (
    NanoBananaTextToImage,
    NanoBananaImageToImage,
    NanoBananaBatchProcessor,
    # Test nodes for Gemini 3 Pro Image Preview
    Gemini3TextToImageTest,
    Gemini3ImageToImageTest,
    Gemini3BatchProcessorTest,
)

# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "NanoBananaTextToImage": NanoBananaTextToImage,
    "NanoBananaImageToImage": NanoBananaImageToImage,
    "NanoBananaBatchProcessor": NanoBananaBatchProcessor,
    # Test nodes
    "Gemini3TextToImageTest": Gemini3TextToImageTest,
    "Gemini3ImageToImageTest": Gemini3ImageToImageTest,
    "Gemini3BatchProcessorTest": Gemini3BatchProcessorTest,
}

# Node display names in ComfyUI interface
NODE_DISPLAY_NAME_MAPPINGS = {
    "NanoBananaTextToImage": "Nano Banana 文生图",
    "NanoBananaImageToImage": "Nano Banana 图生图",
    "NanoBananaBatchProcessor": "Nano Banana 批量处理",
    # Test nodes
    "Gemini3TextToImageTest": "Gemini 3 文生图 (测试)",
    "Gemini3ImageToImageTest": "Gemini 3 图生图 (测试)",
    "Gemini3BatchProcessorTest": "Gemini 3 批量处理 (测试)",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
__version__ = "1.3.0"

# Print initialization message
print("🍌 Comfyui_o1key v1.3.0 加载成功!")
print("   - Nano Banana 文生图")
print("   - Nano Banana 图生图")
print("   - Nano Banana 批量处理")
print("   - Gemini 3 文生图 (测试)")
print("   - Gemini 3 图生图 (测试)")
print("   - Gemini 3 批量处理 (测试)")
print("   - Powered by o1key.com")
