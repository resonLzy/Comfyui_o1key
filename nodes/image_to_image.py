"""
ComfyUI node for image-to-image generation using Nano Banana API
"""
import logging

# Try relative import first (when used as package), fallback to absolute
try:
    from ..utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image,
        comfy_image_to_base64
    )
except ImportError:
    from utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image,
        comfy_image_to_base64
    )

logger = logging.getLogger(__name__)


class NanoBananaImageToImage:
    """
    ComfyUI node for image-to-image generation using Nano Banana API
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "transform this into a watercolor painting"
                }),
                "api_key": ("STRING", {
                    "multiline": False,
                    "default": ""
                }),
                "model": ([
                    "nano-banana-pro-default",
                    "nano-banana-pro-svip", 
                    "nano-banana-svip"
                ], {
                    "default": "nano-banana-pro-default"
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
                "image_2": ("IMAGE",),
                "image_3": ("IMAGE",),
                "image_4": ("IMAGE",),
                "image_5": ("IMAGE",),
                "image_6": ("IMAGE",),
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
    
    def generate_image(self, image, prompt, api_key, model, aspect_ratio, image_size="2K", image_2=None, image_3=None, image_4=None, image_5=None, image_6=None, seed=-1):
        """
        Generate image from reference image and text prompt
        """
        try:
            # Process seed (-1 means random)
            seed_param = None if seed < 0 else seed
            
            # 收集所有参考图
            reference_images = [image]
            if image_2 is not None:
                reference_images.append(image_2)
            if image_3 is not None:
                reference_images.append(image_3)
            if image_4 is not None:
                reference_images.append(image_4)
            if image_5 is not None:
                reference_images.append(image_5)
            if image_6 is not None:
                reference_images.append(image_6)
            
            num_references = len(reference_images)

            print(f"\n{'='*60}")
            print(f"Nano Banana 图生图")
            print(f"{'='*60}")
            print(f"提示词    {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
            print(f"模型      {model}")
            print(f"宽高比    {aspect_ratio}")
            print(f"清晰度    {image_size}")
            print(f"参考图    {num_references} 张")
            for idx, ref_img in enumerate(reference_images, 1):
                print(f"  - 参考图{idx}: {ref_img.shape[2]}x{ref_img.shape[1]}")
            print(f"{'='*60}\n")
            
            logger.debug(f"Total reference images: {num_references}")
            
            # Convert all reference images to base64
            reference_base64_list = []
            for ref_img in reference_images:
                reference_base64_list.append(comfy_image_to_base64(ref_img))
            
            # 状态1: 正在转换（开始）
            print(f"📝 正在转换")
            
            # 状态2: 等待API返回（调用API前）
            print(f"⏳ 耐心等待，好饭不怕晚...")
            
            # 调用API（image_size会由API函数内部判断是否使用）
            response_data = call_nano_banana_api(
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                seed=seed_param,
                api_key=api_key,
                reference_images_base64=reference_base64_list
            )

            # API返回200后，处理图片
            pil_image = process_api_response(response_data)
            comfy_image = pil_to_comfy_image(pil_image)
            
            # 状态3: 完成
            print(f"✅ 完成：改造完成！")
            print(f"\n🎉 图生图完成! 您的作品华丽变身!\n")

            return (comfy_image,)
            
        except Exception as e:
            error_msg = f"图生图失败: {str(e)}"
            print(f"\n{error_msg}\n")
            logger.error(error_msg)
            raise Exception(error_msg)
