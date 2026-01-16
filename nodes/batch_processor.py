"""
ComfyUI node for batch processing images using Nano Banana API
"""
import logging
import time
from comfy.utils import ProgressBar

# Try relative import first (when used as package), fallback to absolute
try:
    from ..utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image,
        comfy_image_to_base64,
        load_images_from_folder,
        save_image_to_folder,
        format_time,
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
        load_images_from_folder,
        save_image_to_folder,
        format_time,
        resize_image_to_max_dim,
        UPSCALE_METHODS,
        MAX_DIM_OPTIONS,
        sanitize_error_message
    )

logger = logging.getLogger(__name__)


class NanoBananaBatchProcessor:
    """
    批量处理节点：从文件夹批量处理图片，支持多提示词
    
    特性：
    - 批量处理：自动遍历文件夹中的图片
    - 多提示词：支持多行提示词，每行一个
    - 自动重试：API 内置重试机制，遇到服务器错误会自动重试
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "提示词": ("STRING", {
                    "multiline": True,
                    "default": "enhance this image\n每行一个提示词，支持多批次处理"
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
                "输入文件夹": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
                "文件匹配": ("STRING", {
                    "default": "*.png,*.jpg,*.jpeg",
                    "multiline": False
                }),
                "输出文件夹": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
            },
            "optional": {
                # 参考图
                "参考图_1": ("IMAGE",),
                "参考图_2": ("IMAGE",),
                "参考图_3": ("IMAGE",),
                "参考图_4": ("IMAGE",),
                "参考图_5": ("IMAGE",),
                "参考图_6": ("IMAGE",),
                "参考图_7": ("IMAGE",),
                "参考图_8": ("IMAGE",),
                "参考图_9": ("IMAGE",),
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
    RETURN_NAMES = ("images",)
    FUNCTION = "process_batch"
    CATEGORY = "o1key/batch"
    
    def process_batch(self, 提示词, 模型, 宽高比, 分辨率, 缩放方法, 最大尺寸,
                     输入文件夹, 文件匹配, 输出文件夹,
                     参考图_1=None, 参考图_2=None, 参考图_3=None, 
                     参考图_4=None, 参考图_5=None, 参考图_6=None,
                     参考图_7=None, 参考图_8=None, 参考图_9=None,
                     种子=-1, 生成后控制="randomize", api_config=None):
        """
        批量处理文件夹中的图片，支持多提示词
        
        Args:
            缩放方法: 缩放方法 (lanczos, bilinear, bicubic 等)
            最大尺寸: 最大尺寸，"auto" 表示不缩放
        """
        # 参数映射（方便内部使用英文变量名）
        prompt = 提示词
        model = 模型
        aspect_ratio = 宽高比
        image_size = 分辨率
        upscale_method = 缩放方法
        max_dim = 最大尺寸
        folder_path = 输入文件夹
        file_pattern = 文件匹配
        output_folder = 输出文件夹
        image_1 = 参考图_1
        image_2 = 参考图_2
        image_3 = 参考图_3
        image_4 = 参考图_4
        image_5 = 参考图_5
        image_6 = 参考图_6
        image_7 = 参考图_7
        image_8 = 参考图_8
        image_9 = 参考图_9
        seed = 种子
        control_after_generation = 生成后控制  # 保留参数以保持兼容性
        
        try:
            import random
            import torch
            
            # 从配置节点获取配置信息
            if api_config and isinstance(api_config, (tuple, list)) and len(api_config) >= 3:
                final_api_key, final_network_url, final_proxy = api_config[0], api_config[1], api_config[2]
            else:
                raise ValueError("请连接API配置节点，提供API密钥、网络线路和代理设置")
            
            # 解析提示词（每行一个）
            prompts = [p.strip() for p in prompt.split('\n') if p.strip()]
            if len(prompts) == 0:
                raise ValueError("至少需要提供一个提示词")
            
            # 初始化种子
            current_seed = seed if seed >= 0 else random.randint(0, 2147483647)
            
            # 收集固定参考图
            fixed_refs = []
            for img in [image_1, image_2, image_3, image_4, image_5, image_6, image_7, image_8, image_9]:
                if img is not None:
                    fixed_refs.append(img)
            
            num_fixed_refs = len(fixed_refs)
            
            # 加载文件夹中的图片
            pil_images, filenames = load_images_from_folder(folder_path, file_pattern)
            
            if len(pil_images) == 0:
                raise Exception(f"在文件夹 {folder_path} 中未找到图片")
            
            total_images = len(pil_images)
            total_prompts = len(prompts)
            total_generations = total_images * total_prompts
            
            # 统计数据
            success_count = 0
            failed_count = 0
            start_time = time.time()
            
            # 打印任务信息
            print(f"\n{'='*60}")
            print(f"🍌 Nano Banana 批量处理")
            print(f"{'='*60}")
            print(f"📁 文件夹    {folder_path}")
            print(f"📝 提示词    {len(prompts)} 个")
            for idx, p in enumerate(prompts, 1):
                print(f"   {idx}. {p[:50]}{'...' if len(p) > 50 else ''}")
            print(f"🤖 模型      {model}")
            print(f"📐 宽高比    {aspect_ratio}")
            print(f"🖼️  分辨率    {image_size}")
            if num_fixed_refs > 0:
                print(f"🖼️  参考图    {num_fixed_refs} 张")
            if max_dim != "auto":
                print(f"📐 缩放      最大 {max_dim}px ({upscale_method})")
            print(f"{'='*60}")
            print(f"📊 任务: {total_images}张 × {total_prompts}提示词 = {total_generations}个")
            print(f"{'='*60}\n")
            
            # 批量处理
            all_processed_images = []
            pbar = ProgressBar(total_generations)
            processed_count = 0
            
            # 外层循环：遍历提示词
            for prompt_idx, current_prompt in enumerate(prompts, 1):
                if total_prompts > 1:
                    print(f"\n{'─'*60}")
                    print(f"📝 提示词 [{prompt_idx}/{total_prompts}]: {current_prompt[:60]}{'...' if len(current_prompt) > 60 else ''}")
                    print(f"{'─'*60}")
                
                # 内层循环：遍历文件夹图片
                for img_idx, (pil_img, filename) in enumerate(zip(pil_images, filenames), 1):
                    processed_count += 1
                    progress_pct = processed_count / total_generations * 100
                    
                    print(f"\n🔄 [{processed_count}/{total_generations}] ({progress_pct:.0f}%) {filename}")
                    
                    # 记录单次处理开始时间
                    task_start = time.time()
                    
                    try:
                        # 将当前图片转为ComfyUI格式
                        current_image_tensor = pil_to_comfy_image(pil_img)
                        
                        # 组合参考图
                        all_refs = fixed_refs + [current_image_tensor]
                        
                        # 转换为base64
                        ref_base64_list = [comfy_image_to_base64(ref) for ref in all_refs]
                        
                        # 处理种子参数
                        seed_param = None if current_seed < 0 else current_seed
                        
                        # 调用API
                        response_data = call_nano_banana_api(
                            prompt=current_prompt,
                            model=model,
                            aspect_ratio=aspect_ratio,
                            image_size=image_size,
                            seed=seed_param,
                            api_key=final_api_key,
                            reference_images_base64=ref_base64_list,
                            response_format=None,  # 后端自动适配
                            proxy=final_proxy,
                            network_url=final_network_url
                        )
                        
                        # 处理响应
                        result_pil = process_api_response(response_data, proxy=final_proxy)
                        
                        # 应用缩放（如果不是 auto）
                        if max_dim != "auto":
                            original_size = result_pil.size
                            result_pil = resize_image_to_max_dim(result_pil, max_dim, upscale_method)
                            if result_pil.size != original_size:
                                print(f"   📐 缩放: {original_size[0]}x{original_size[1]} -> {result_pil.size[0]}x{result_pil.size[1]}")
                        
                        result_comfy = pil_to_comfy_image(result_pil)
                        all_processed_images.append(result_comfy)
                        
                        # 保存到输出文件夹
                        if output_folder:
                            prefix = f"prompt{prompt_idx}_" if total_prompts > 1 else ""
                            save_filename = prefix + filename
                            save_image_to_folder(result_pil, output_folder, save_filename)
                        
                        # 记录成功
                        task_time = time.time() - task_start
                        success_count += 1
                        print(f"   ✅ 成功 ({task_time:.1f}秒)")
                        
                    except Exception as e:
                        error_str = str(e)
                        failed_count += 1
                        
                        # 清理敏感信息后显示错误信息
                        sanitized_error = sanitize_error_message(error_str)
                        short_error = sanitized_error[:100] if len(sanitized_error) > 100 else sanitized_error
                        print(f"   ❌ 失败: {short_error}")
                        
                        # 检测服务器过载，提醒用户
                        if "429" in error_str or "503" in error_str or "502" in error_str or "频繁" in error_str:
                            print(f"   ⚠️ 服务器压力较大，API 内置重试机制会自动处理")
                        
                        logger.error(f"处理失败 {filename}: {sanitized_error}")
                    
                    pbar.update(1)
            
            # 汇总结果
            total_time = time.time() - start_time
            success_rate = (success_count / total_generations * 100) if total_generations > 0 else 0
            avg_time = total_time / max(success_count, 1)
            
            print(f"\n{'='*60}")
            print(f"🎉 批量处理完成!")
            print(f"{'='*60}")
            print(f"📊 成功: {success_count}/{total_generations} ({success_rate:.0f}%)")
            if failed_count > 0:
                print(f"   失败: {failed_count}")
            print(f"⏱️  总耗时: {format_time(total_time)}")
            print(f"   平均: {avg_time:.1f}秒/张")
            if output_folder:
                print(f"💾 保存: {output_folder}")
            print(f"{'='*60}\n")
            
            if len(all_processed_images) == 0:
                raise Exception("所有图片处理失败，请检查API状态或稍后重试")
            
            # 合并为batch返回
            result_batch = torch.cat(all_processed_images, dim=0)
            
            return (result_batch,)
            
        except Exception as e:
            error_msg = f"批量处理失败: {str(e)}"
            sanitized_msg = sanitize_error_message(error_msg)
            print(f"\n❌ {sanitized_msg}\n")
            logger.error(sanitized_msg)
            raise Exception(sanitized_msg)
