"""
ComfyUI node for image-to-image generation using Nano Banana API
"""
import logging
import time

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
                "model": ([
                    "nano-banana-pro-default",
                    "gemini-3-pro-image-preview-url",
                    "gemini-3-pro-image-preview-2k-url",
                    "gemini-3-pro-image-preview-4k-url",
                    "gemini-3-pro-image-preview",
                    "gemini-3-pro-image-preview-2k",
                    "gemini-3-pro-image-preview-4k",
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
                "response_format": (["url", "b64_json"], {
                    "default": "url"
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
                "api_key": ("STRING", {
                    "multiline": False,
                    "default": ""
                }),
                "proxy": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "placeholder": "http://127.0.0.1:7890"
                }),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "generate_image"
    CATEGORY = "o1key"
    
    def generate_image(self, image, prompt, model, aspect_ratio, image_size="2K", response_format="url", image_2=None, image_3=None, image_4=None, image_5=None, image_6=None, seed=-1, api_key="", proxy=""):
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
            print(f"返回格式  {response_format}")
            print(f"参考图    {num_references} 张")
            for idx, ref_img in enumerate(reference_images, 1):
                print(f"  - 参考图{idx}: {ref_img.shape[2]}x{ref_img.shape[1]}")
            print(f"{'='*60}\n")
            
            logger.debug(f"Total reference images: {num_references}")
            
            _start_total = time.time()
            
            # ========== 阶段1: 图片转 Base64 ==========
            print(f"\n⏱️  [阶段1] 图片转 Base64...", flush=True)
            _t1 = time.time()
            reference_base64_list = []
            for idx, ref_img in enumerate(reference_images, 1):
                _t_conv = time.time()
                b64 = comfy_image_to_base64(ref_img)
                reference_base64_list.append(b64)
                print(f"    图{idx}: {len(b64)/1024:.0f} KB ({time.time()-_t_conv:.2f}s)", flush=True)
            print(f"    ✅ 阶段1完成: {time.time()-_t1:.2f}s", flush=True)
            
            # ========== 阶段2: 调用API ==========
            print(f"\n⏱️  [阶段2] 调用 API...", flush=True)
            _t2 = time.time()
            
            response_data = call_nano_banana_api(
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                seed=seed_param,
                api_key=api_key,
                reference_images_base64=reference_base64_list,
                response_format=response_format,
                proxy=proxy
            )
            print(f"    ✅ 阶段2完成: {time.time()-_t2:.2f}s", flush=True)

            # ========== 阶段3: 处理响应 ==========
            print(f"\n⏱️  [阶段3] 处理响应...", flush=True)
            _t3 = time.time()
            pil_image = process_api_response(response_data, proxy=proxy)
            print(f"    ✅ 阶段3完成: {time.time()-_t3:.2f}s", flush=True)
            
            # ========== 阶段4: 转换格式 ==========
            print(f"\n⏱️  [阶段4] 转 ComfyUI 格式...", flush=True)
            _t4 = time.time()
            comfy_image = pil_to_comfy_image(pil_image)
            print(f"    ✅ 阶段4完成: {time.time()-_t4:.2f}s", flush=True)
            
            print(f"\n{'='*50}", flush=True)
            print(f"⏱️  本地总耗时: {time.time()-_start_total:.2f}s", flush=True)
            print(f"{'='*50}", flush=True)
            
            # 状态3: 完成
            print(f"✅ 完成：改造完成！")
            print(f"\n🎉 图生图完成! 您的作品华丽变身!\n")

            return (comfy_image,)
            
        except Exception as e:
            error_msg = f"图生图失败: {str(e)}"
            print(f"\n{error_msg}\n")
            logger.error(error_msg)
            raise Exception(error_msg)
