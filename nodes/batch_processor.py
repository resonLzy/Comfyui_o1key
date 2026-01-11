"""
ComfyUI node for batch processing images using Nano Banana API
"""
import logging
from comfy.utils import ProgressBar

# Try relative import first (when used as package), fallback to absolute
try:
    from ..utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image,
        comfy_image_to_base64,
        load_images_from_folder,
        save_image_to_folder
    )
except ImportError:
    from utils import (
        call_nano_banana_api,
        process_api_response,
        pil_to_comfy_image,
        comfy_image_to_base64,
        load_images_from_folder,
        save_image_to_folder
    )

logger = logging.getLogger(__name__)


class NanoBananaBatchProcessor:
    """
    批量处理节点：从文件夹批量处理图片，支持多提示词
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
                     image_1=None, image_2=None, image_3=None, 
                     image_4=None, image_5=None, image_6=None):
        """
        批量处理文件夹中的图片，支持多提示词
        """
        try:
            import random
            
            # 解析提示词（每行一个）
            prompts = [p.strip() for p in prompt.split('\n') if p.strip()]
            if len(prompts) == 0:
                raise ValueError("至少需要提供一个提示词")
            
            # 初始化种子
            current_seed = seed if seed >= 0 else random.randint(0, 2147483647)
            
            # 收集固定参考图
            fixed_refs = []
            if image_1 is not None:
                fixed_refs.append(image_1)
            if image_2 is not None:
                fixed_refs.append(image_2)
            if image_3 is not None:
                fixed_refs.append(image_3)
            if image_4 is not None:
                fixed_refs.append(image_4)
            if image_5 is not None:
                fixed_refs.append(image_5)
            if image_6 is not None:
                fixed_refs.append(image_6)
            
            num_fixed_refs = len(fixed_refs)
            
            print(f"\n{'='*60}")
            print(f"Nano Banana 批量处理")
            print(f"{'='*60}")
            print(f"文件夹    {folder_path}")
            print(f"提示词数  {len(prompts)} 个")
            for idx, p in enumerate(prompts, 1):
                print(f"  {idx}. {p[:60]}{'...' if len(p) > 60 else ''}")
            print(f"模型      {model}")
            print(f"宽高比    {aspect_ratio}")
            print(f"清晰度    {image_size}")
            print(f"固定参考图 {num_fixed_refs} 张")
            print(f"文件过滤  {file_pattern}")
            if output_folder:
                print(f"输出文件夹 {output_folder}")
            print(f"{'='*60}\n")
            
            # 加载文件夹中的图片
            pil_images, filenames = load_images_from_folder(folder_path, file_pattern)
            
            if len(pil_images) == 0:
                raise Exception(f"在文件夹 {folder_path} 中未找到图片")
            
            total_images = len(pil_images)
            total_prompts = len(prompts)
            total_generations = total_images * total_prompts
            
            print(f"📋 找到 {total_images} 张图片")
            print(f"📋 共 {total_prompts} 个提示词")
            print(f"📋 总计需要生成 {total_generations} 张图片\n")
            
            # 批量处理
            all_processed_images = []
            failed_count = 0
            success_count = 0
            pbar = ProgressBar(total_generations)
            
            # 外层循环：遍历提示词
            for prompt_idx, current_prompt in enumerate(prompts, 1):
                print(f"\n{'='*60}")
                print(f"📝 提示词批次 [{prompt_idx}/{total_prompts}]")
                print(f"提示词: {current_prompt[:80]}{'...' if len(current_prompt) > 80 else ''}")
                print(f"{'='*60}\n")
                
                # 内层循环：遍历文件夹图片
                for img_idx, (pil_img, filename) in enumerate(zip(pil_images, filenames), 1):
                    try:
                        print(f"📝 [{prompt_idx}/{total_prompts}] [{img_idx}/{total_images}] 处理: {filename}")
                        print(f"⏳ 使用种子: {current_seed} | 耐心等待...")
                        
                        # 将当前图片转为ComfyUI格式
                        current_image_tensor = pil_to_comfy_image(pil_img)
                        
                        # 组合参考图：固定参考图 + 当前图片
                        all_refs = fixed_refs + [current_image_tensor]
                        
                        # 转换所有参考图为base64
                        ref_base64_list = []
                        for ref in all_refs:
                            ref_base64_list.append(comfy_image_to_base64(ref))
                        
                        # 处理种子参数
                        seed_param = None if current_seed < 0 else current_seed
                        
                        # 调用API（image_size会由API函数内部判断是否使用）
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
                        
                        # 保存到输出文件夹（如果指定）
                        if output_folder:
                            # 添加批次前缀到文件名
                            prefix = f"prompt{prompt_idx}_"
                            save_filename = prefix + filename
                            save_image_to_folder(result_pil, output_folder, save_filename)
                        
                        print(f"✅ 完成: {filename}\n")
                        success_count += 1
                        
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"处理失败 [{prompt_idx}/{total_prompts}] {filename}: {str(e)}")
                        print(f"❌ 失败: {filename} - {str(e)}\n")
                        # 继续处理下一张
                    
                    pbar.update(1)
            
            # 汇总结果
            print(f"\n{'='*60}")
            print(f"🎉 批量处理完成!")
            print(f"提示词数: {total_prompts}")
            print(f"图片数:   {total_images}")
            print(f"总生成数: {total_generations}")
            print(f"成功:     {success_count}/{total_generations}")
            if failed_count > 0:
                print(f"失败:     {failed_count}")
            if output_folder:
                print(f"保存位置: {output_folder}")
            print(f"{'='*60}\n")
            
            if len(all_processed_images) == 0:
                raise Exception("所有图片处理失败")
            
            # 合并为batch返回
            import torch
            result_batch = torch.cat(all_processed_images, dim=0)
            
            return (result_batch,)
            
        except Exception as e:
            error_msg = f"批量处理失败: {str(e)}"
            print(f"\n{error_msg}\n")
            logger.error(error_msg)
            raise Exception(error_msg)
