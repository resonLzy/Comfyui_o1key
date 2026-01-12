"""
ComfyUI node for batch processing images using Nano Banana API
使用 BatchRequestManager 进行智能限流
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
        BatchRequestManager,
        format_time
    )
except ImportError:
    from utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image,
        comfy_image_to_base64,
        load_images_from_folder,
        save_image_to_folder,
        BatchRequestManager,
        format_time
    )

logger = logging.getLogger(__name__)


class NanoBananaBatchProcessor:
    """
    批量处理节点：从文件夹批量处理图片，支持多提示词
    
    特性：
    - 智能限流：自动控制请求频率，防止服务器过载
    - 自适应调整：遇到限流错误时自动降速
    - 进度预估：实时显示预计完成时间
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "enhance this image\n每行一个提示词，支持多批次处理"
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
                "folder_path": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
                "file_pattern": ("STRING", {
                    "default": "*.png,*.jpg,*.jpeg",
                    "multiline": False
                }),
                "output_folder": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
            },
            "optional": {
                "seed": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 2147483647,
                    "display": "number"
                }),
                "request_interval": ("FLOAT", {
                    "default": 1.5,
                    "min": 0.5,
                    "max": 10.0,
                    "step": 0.5,
                    "display": "number",
                    "tooltip": "每个请求之间的间隔（秒），建议1-3秒"
                }),
                # 参考图
                "image_1": ("IMAGE",),
                "image_2": ("IMAGE",),
                "image_3": ("IMAGE",),
                "image_4": ("IMAGE",),
                "image_5": ("IMAGE",),
                "image_6": ("IMAGE",),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "process_batch"
    CATEGORY = "o1key/batch"
    
    def process_batch(self, prompt, api_key, model, aspect_ratio, image_size, 
                     folder_path, file_pattern, output_folder,
                     seed=-1,
                     request_interval=1.5,
                     image_1=None, image_2=None, image_3=None, 
                     image_4=None, image_5=None, image_6=None):
        """
        批量处理文件夹中的图片，支持多提示词
        """
        try:
            import random
            import torch
            
            # 解析提示词（每行一个）
            prompts = [p.strip() for p in prompt.split('\n') if p.strip()]
            if len(prompts) == 0:
                raise ValueError("至少需要提供一个提示词")
            
            # 初始化种子
            current_seed = seed if seed >= 0 else random.randint(0, 2147483647)
            
            # 收集固定参考图
            fixed_refs = []
            for img in [image_1, image_2, image_3, image_4, image_5, image_6]:
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
            
            # 初始化批量请求管理器
            batch_manager = BatchRequestManager(request_interval=request_interval)
            batch_manager.start(total_generations)
            
            # 预估总时间
            avg_generation_time = 15  # 假设平均每张15秒
            estimated_total = total_generations * (avg_generation_time + request_interval)
            
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
            print(f"🖼️  清晰度    {image_size}")
            if num_fixed_refs > 0:
                print(f"🖼️  固定参考  {num_fixed_refs} 张")
            print(f"{'='*60}")
            print(f"📊 任务: {total_images}张 × {total_prompts}提示词 = {total_generations}个")
            print(f"⏱️  预计耗时: {format_time(estimated_total)}")
            print(f"🚦 请求间隔: {request_interval}秒")
            print(f"{'='*60}\n")
            
            # 批量处理
            all_processed_images = []
            pbar = ProgressBar(total_generations)
            
            # 外层循环：遍历提示词
            for prompt_idx, current_prompt in enumerate(prompts, 1):
                if total_prompts > 1:
                    print(f"\n{'─'*60}")
                    print(f"📝 提示词 [{prompt_idx}/{total_prompts}]: {current_prompt[:60]}{'...' if len(current_prompt) > 60 else ''}")
                    print(f"{'─'*60}")
                
                # 内层循环：遍历文件夹图片
                for img_idx, (pil_img, filename) in enumerate(zip(pil_images, filenames), 1):
                    
                    # 获取进度信息
                    progress = batch_manager.get_progress_info()
                    eta_str = batch_manager.format_eta()
                    
                    print(f"\n🔄 [{progress['processed']+1}/{progress['total']}] ({progress['progress_pct']:.0f}%) {filename}")
                    print(f"   预计剩余: {eta_str}")
                    
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
                            api_key=api_key,
                            reference_images_base64=ref_base64_list
                        )
                        
                        # 处理响应
                        result_pil = process_api_response(response_data)
                        result_comfy = pil_to_comfy_image(result_pil)
                        all_processed_images.append(result_comfy)
                        
                        # 保存到输出文件夹
                        if output_folder:
                            prefix = f"prompt{prompt_idx}_" if total_prompts > 1 else ""
                            save_filename = prefix + filename
                            save_image_to_folder(result_pil, output_folder, save_filename)
                        
                        # 记录成功
                        task_time = time.time() - task_start
                        batch_manager.record_success(processing_time=task_time)
                        print(f"   ✅ 成功 ({task_time:.1f}秒)")
                        
                    except Exception as e:
                        error_str = str(e)
                        is_rate_limit = BatchRequestManager.is_rate_limit_error(error_str)
                        batch_manager.record_failure(is_rate_limit=is_rate_limit)
                        
                        # 显示简短错误
                        short_error = error_str[:80] if len(error_str) > 80 else error_str
                        print(f"   ❌ 失败: {short_error}")
                        
                        if is_rate_limit:
                            print(f"   ⚠️ 触发限流，自动降速")
                        
                        logger.error(f"处理失败 {filename}: {error_str}")
                    
                    pbar.update(1)
                    
                    # 等待下次请求
                    wait_time = batch_manager.wait_before_next()
                    if wait_time > 0:
                        print(f"   ⏳ 等待 {wait_time:.1f}秒")
            
            # 汇总结果
            summary = batch_manager.get_summary()
            
            print(f"\n{'='*60}")
            print(f"🎉 批量处理完成!")
            print(f"{'='*60}")
            print(f"📊 成功: {summary['success']}/{summary['total']} ({summary['success_rate']:.0f}%)")
            if summary['failed'] > 0:
                print(f"   失败: {summary['failed']}")
            print(f"⏱️  总耗时: {format_time(summary['total_time_seconds'])}")
            print(f"   平均: {summary['avg_time_seconds']:.1f}秒/张")
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
            print(f"\n❌ {error_msg}\n")
            logger.error(error_msg)
            raise Exception(error_msg)
