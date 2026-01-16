"""
ComfyUI node for image-to-image generation using Nano Banana API
"""
import logging
import time
import torch
from concurrent.futures import ThreadPoolExecutor, as_completed

# Try relative import first (when used as package), fallback to absolute
try:
    from ..utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image,
        comfy_image_to_base64,
        resize_image_to_max_dim,
        UPSCALE_METHODS,
        MAX_DIM_OPTIONS,
        sanitize_error_message
    )
except ImportError:
    from utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image,
        comfy_image_to_base64,
        resize_image_to_max_dim,
        UPSCALE_METHODS,
        MAX_DIM_OPTIONS,
        sanitize_error_message
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
                "图像": ("IMAGE",),
                "提示词": ("STRING", {
                    "multiline": True,
                    "default": "transform this into a watercolor painting"
                }),
                "模型": ([
                    "gemini-3-pro-image-preview-url",
                ], {
                    "default": "gemini-3-pro-image-preview-url"
                }),
                "宽高比": ([
                    "1:1", "4:3", "3:4", "16:9", "9:16", 
                    "2:3", "3:2", "4:5", "5:4", "21:9"
                ], {
                    "default": "1:1"
                }),
                "分辨率": (["1K", "2K", "4K"], {
                    "default": "2K"
                }),
                "缩放方法": (list(UPSCALE_METHODS.keys()), {
                    "default": "lanczos"
                }),
                "最大尺寸": (MAX_DIM_OPTIONS, {
                    "default": "auto"
                }),
            },
            "optional": {
                "图像_2": ("IMAGE",),
                "图像_3": ("IMAGE",),
                "图像_4": ("IMAGE",),
                "图像_5": ("IMAGE",),
                "图像_6": ("IMAGE",),
                "图像_7": ("IMAGE",),
                "图像_8": ("IMAGE",),
                "图像_9": ("IMAGE",),
                "批次大小": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                    "display": "number"
                }),
                "种子": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 2147483647,
                    "display": "number"
                }),
                "生成后控制": (["randomize", "fixed", "increment", "decrement"], {
                    "default": "randomize"
                }),
                "api_config": ("APICONFIG",),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "generate_image"
    CATEGORY = "o1key"
    
    def _generate_single_image(self, prompt, model, aspect_ratio, image_size, seed_param,
                                final_api_key, final_proxy, final_network_url,
                                reference_base64_list, batch_idx,
                                upscale_method="lanczos", max_dim="auto"):
        """
        生成单张图片（用于并发调用）
        
        Args:
            reference_base64_list: 参考图的base64列表
            batch_idx: 批次索引，用于显示进度
            upscale_method: 缩放方法
            max_dim: 最大尺寸
            
        Returns:
            tuple: (batch_idx, comfy_image, error_msg)
        """
        try:
            # 调用API
            response_data = call_nano_banana_api(
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                seed=seed_param,
                api_key=final_api_key,
                reference_images_base64=reference_base64_list,
                response_format=None,
                proxy=final_proxy,
                network_url=final_network_url
            )

            # 处理响应
            pil_image = process_api_response(response_data, proxy=final_proxy)
            
            # 应用缩放（如果不是 auto）
            if max_dim != "auto":
                pil_image = resize_image_to_max_dim(pil_image, max_dim, upscale_method)
            
            comfy_image = pil_to_comfy_image(pil_image)
            
            return (batch_idx, comfy_image, None)
            
        except Exception as e:
            return (batch_idx, None, str(e))
    
    def generate_image(self, 图像, 提示词, 模型, 宽高比, 分辨率, 缩放方法, 最大尺寸,
                       图像_2=None, 图像_3=None, 图像_4=None, 图像_5=None, 图像_6=None,
                       图像_7=None, 图像_8=None, 图像_9=None,
                       批次大小=1, 种子=-1, 生成后控制="randomize", api_config=None):
        """
        Generate image from reference image and text prompt
        
        Args:
            批次大小: 并发批次大小，同时发送的请求数量
            缩放方法: 缩放方法 (lanczos, bilinear, bicubic 等)
            最大尺寸: 最大尺寸，"auto" 表示不缩放
        """
        # 参数映射（方便内部使用英文变量名）
        image = 图像
        prompt = 提示词
        model = 模型
        aspect_ratio = 宽高比
        image_size = 分辨率
        upscale_method = 缩放方法
        max_dim = 最大尺寸
        image_2 = 图像_2
        image_3 = 图像_3
        image_4 = 图像_4
        image_5 = 图像_5
        image_6 = 图像_6
        image_7 = 图像_7
        image_8 = 图像_8
        image_9 = 图像_9
        batch_size = 批次大小
        seed = 种子
        control_after_generation = 生成后控制  # 保留参数以保持兼容性
        
        try:
            # 从配置节点获取配置信息
            if api_config and isinstance(api_config, (tuple, list)) and len(api_config) >= 3:
                final_api_key = api_config[0]
                final_network_url = api_config[1]
                final_proxy = api_config[2]
                # 获取network名称（如果存在，用于显示）
                final_network_name = api_config[3] if len(api_config) >= 4 else "未知线路"
            else:
                raise ValueError("请连接API配置节点，提供API密钥、网络线路和代理设置")
            
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
            if image_7 is not None:
                reference_images.append(image_7)
            if image_8 is not None:
                reference_images.append(image_8)
            if image_9 is not None:
                reference_images.append(image_9)
            
            num_references = len(reference_images)

            print(f"\n{'='*60}")
            print(f"Nano Banana 图生图")
            print(f"{'='*60}")
            print(f"提示词    {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
            print(f"模型      {model}")
            print(f"宽高比    {aspect_ratio}")
            print(f"分辨率    {image_size}")
            print(f"参考图    {num_references} 张")
            for idx, ref_img in enumerate(reference_images, 1):
                print(f"  - 参考图{idx}: {ref_img.shape[2]}x{ref_img.shape[1]}")
            if batch_size > 1:
                print(f"批次大小  {batch_size} 张")
            if max_dim != "auto":
                print(f"缩放      最大 {max_dim}px ({upscale_method})")
            print(f"{'='*60}\n")
            
            logger.debug(f"Total reference images: {num_references}, Batch size: {batch_size}")
            
            # ========== 阶段1: 图片转 Base64（不输出，耗时极少）==========
            reference_base64_list = []
            for ref_img in reference_images:
                b64 = comfy_image_to_base64(ref_img)
                reference_base64_list.append(b64)
            
            # 记录开始时间
            _t_start = time.time()
            
            if batch_size == 1:
                # 单张图片生成（原有逻辑）
                response_data = call_nano_banana_api(
                    prompt=prompt,
                    model=model,
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                    seed=seed_param,
                    api_key=final_api_key,
                    reference_images_base64=reference_base64_list,
                    response_format=None,
                    proxy=final_proxy,
                    network_url=final_network_url
                )

                pil_image = process_api_response(response_data, proxy=final_proxy)
                
                # 应用缩放（如果不是 auto）
                if max_dim != "auto":
                    original_size = pil_image.size
                    pil_image = resize_image_to_max_dim(pil_image, max_dim, upscale_method)
                    if pil_image.size != original_size:
                        print(f"📐 图像已缩放: {original_size[0]}x{original_size[1]} -> {pil_image.size[0]}x{pil_image.size[1]}")
                
                comfy_image = pil_to_comfy_image(pil_image)
                
                total_time = time.time() - _t_start
                print(f"\n🎉 出图完成！：总耗时 {total_time:.2f}秒\n")

                return (comfy_image,)
            else:
                # 并发批量生成
                print(f"📝 正在并发生成 {batch_size} 张图片...")
                print(f"⏳ 耐心等待，好饭不怕晚...")
                
                all_images = []
                success_count = 0
                failed_count = 0
                errors = []
                
                # 使用线程池并发执行
                with ThreadPoolExecutor(max_workers=batch_size) as executor:
                    # 提交所有任务
                    futures = []
                    for i in range(batch_size):
                        future = executor.submit(
                            self._generate_single_image,
                            prompt, model, aspect_ratio, image_size, seed_param,
                            final_api_key, final_proxy, final_network_url,
                            reference_base64_list, i + 1,
                            upscale_method, max_dim
                        )
                        futures.append(future)
                    
                    # 等待所有任务完成，按完成顺序处理结果
                    for future in as_completed(futures):
                        batch_idx, comfy_image, error_msg = future.result()
                        
                        if comfy_image is not None:
                            all_images.append((batch_idx, comfy_image))
                            success_count += 1
                            print(f"   ✅ 图片 {batch_idx} 生成成功")
                        else:
                            failed_count += 1
                            sanitized_error = sanitize_error_message(error_msg)
                            errors.append(f"图片 {batch_idx}: {sanitized_error}")
                            print(f"   ❌ 图片 {batch_idx} 生成失败: {sanitized_error[:50]}...")
                
                total_time = time.time() - _t_start
                
                # 检查是否全部失败
                if success_count == 0:
                    error_detail = "\n".join(errors[:3])  # 只显示前3个错误
                    sanitized_detail = sanitize_error_message(error_detail)
                    raise Exception(f"所有图片生成失败:\n{sanitized_detail}")
                
                # 按批次索引排序，确保顺序一致
                all_images.sort(key=lambda x: x[0])
                sorted_images = [img for _, img in all_images]
                
                # 合并所有图片到一个批次
                result_batch = torch.cat(sorted_images, dim=0)
                
                print(f"\n🎉 出图完成！：成功 {success_count}/{batch_size} 张，总耗时 {total_time:.2f}秒\n")
                
                if failed_count > 0:
                    print(f"⚠️ 失败 {failed_count} 张:")
                    for err in errors[:3]:
                        print(f"   - {err[:80]}")
                    print()

                return (result_batch,)
            
        except Exception as e:
            error_msg = f"图生图失败: {str(e)}"
            sanitized_msg = sanitize_error_message(error_msg)
            print(f"\n{sanitized_msg}\n")
            logger.error(sanitized_msg)
            raise Exception(sanitized_msg)
