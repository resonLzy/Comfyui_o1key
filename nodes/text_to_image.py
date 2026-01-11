"""
ComfyUI node for text-to-image generation using Nano Banana API
"""
import logging

# Try relative import first (when used as package), fallback to absolute
try:
    from ..utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image
    )
except ImportError:
    from utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image
    )

logger = logging.getLogger(__name__)


class NanoBananaTextToImage:
    """
    ComfyUI node for text-to-image generation using Nano Banana API
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "a beautiful sunset over mountains"
                }),
                "api_key": ("STRING", {
                    "multiline": False,
                    "default": ""
                }),
                "model": (["nano-banana-pro-svip", "nano-banana-svip"], {
                    "default": "nano-banana-pro-svip"
                }),
                "aspect_ratio": ([
                    "1:1", "4:3", "3:4", "16:9", "9:16", 
                    "2:3", "3:2", "4:5", "5:4", "21:9"
                ], {
                    "default": "1:1"
                }),
                "image_size": (["1K", "2K", "4K"], {
                    "default": "2K"
                }),
            },
            "optional": {
                "seed": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 2147483647,
                    "display": "number"
                }),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "generate_image"
    CATEGORY = "o1key"
    
    def generate_image(self, prompt, api_key, model, aspect_ratio, image_size="2K", seed=-1):
        """
        Generate image from text prompt
        """
        try:
            # Process seed (-1 means random)
            seed_param = None if seed < 0 else seed

            print(f"\n{'='*60}")
            print(f"Nano Banana 文生图")
            print(f"{'='*60}")
            print(f"提示词    {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
            print(f"模型      {model}")
            print(f"宽高比    {aspect_ratio}")
            print(f"清晰度    {image_size}")
            print(f"{'='*60}\n")
            
            logger.debug(f"Full params - Model: {model}, Aspect: {aspect_ratio}, Size: {image_size}")
            
            # 状态1: 正在生图（开始）
            print(f"📝 正在生图")
            
            # 状态2: 等待API返回（调用API前）
            print(f"⏳ 耐心等待，好饭不怕晚...")
            
            # 调用API（image_size会由API函数内部判断是否使用）
            response_data = call_nano_banana_api(
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                seed=seed_param,
                api_key=api_key
            )

            # API返回200后，处理图片
            pil_image = process_api_response(response_data)
            comfy_image = pil_to_comfy_image(pil_image)
            
            # 状态3: 完成
            print(f"✅ 完成：出图啦！")
            print(f"\n🎉 大功告成! 您的艺术品已准备就绪!\n")

            return (comfy_image,)
            
        except Exception as e:
            error_msg = f"文生图失败: {str(e)}"
            print(f"\n{error_msg}\n")
            logger.error(error_msg)
            raise Exception(error_msg)
