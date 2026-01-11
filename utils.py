"""
Utility functions for Gemini Nano Banana API integration
Uses official Gemini API format for full compatibility
"""
import requests
import base64
import io
import numpy as np
import torch
from PIL import Image
import time
import logging
import os
import glob
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model name mapping: UI name -> Official API name
# This allows user-friendly names in the interface while using official names for API calls
MODEL_NAME_MAPPING = {
    "nano-banana-svip": "nano-banana-svip",
    "nano-banana-pro-svip": "nano-banana-pro-svip",
}


def get_official_model_name(display_name):
    """
    Convert user-friendly model name to official API model name
    
    Args:
        display_name (str): User-friendly name (e.g., "nano-banana-pro-svip")
        
    Returns:
        str: Official API name (e.g., "gemini-3-pro-image-preview")
    """
    return MODEL_NAME_MAPPING.get(display_name, display_name)


def call_nano_banana_api(
    prompt,
    model="nano-banana-pro-svip",
    aspect_ratio="1:1",
    image_size=None,
    seed=None,
    api_key=None,
    reference_images_base64=None,  # 支持多个参考图（列表）
    max_retries=3
):
    """
    Call the Gemini Nano Banana API using official Gemini format
    
    Args:
        prompt (str): The text prompt for image generation
        model (str): Model to use (nano-banana-svip or nano-banana-pro-svip)
        aspect_ratio (str): Aspect ratio for the generated image (1:1, 16:9, etc.)
        image_size (str): Image size (1K, 2K, 4K) - only for nano-banana-pro-svip
        seed (int): Random seed for reproducibility (optional)
        api_key (str): API key for authentication
        reference_images_base64 (list): List of base64 encoded reference images for image-to-image
        max_retries (int): Maximum number of retry attempts
        
    Returns:
        dict: API response containing the generated image
    """
    if not api_key:
        raise ValueError("API key is required")
    
    # Convert user-friendly model name to official API name
    official_model = get_official_model_name(model)
    logger.debug(f"Model mapping: {model} -> {official_model}")
    
    # Build the API endpoint (New API platform format)
    # New API will map model names and proxy to Google AI Studio
    base_url = f"https://o1key.com/v1beta/models/{official_model}:generateContent"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Build request body using official Gemini format
    # Structure: contents -> parts -> text/inline_data
    parts = []
    
    # Add text prompt
    parts.append({"text": prompt})
    
    # Add reference images if provided (for image-to-image)
    if reference_images_base64:
        for ref_base64 in reference_images_base64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": ref_base64
                }
            })
    
    # Build generationConfig following official Gemini API format
    # Structure: generationConfig -> imageConfig -> {aspectRatio, imageSize}
    image_config = {
        "aspectRatio": aspect_ratio
    }
    
    # Add imageSize only for nano-banana-pro-svip model
    # Only this model supports image_size parameter (1K, 2K, 4K)
    if image_size and model == "nano-banana-pro-svip":
        image_config["imageSize"] = image_size
    
    generation_config = {
        "imageConfig": image_config
    }
    # Add seed if provided
    # 注释掉：不再传递种子参数到 API
    # if seed is not None:
    #     generation_config["seed"] = seed
    
    # Complete request body
    body = {
        "contents": [{
            "parts": parts
        }],
        "generationConfig": generation_config
    }
    
    logger.debug(f"Request body structure: {list(body.keys())}")
    logger.debug(f"imageConfig: {image_config}")
    
    #     # === DEBUG: Print full request body ===
    #     import json
    #     print("\n" + "="*80)
    #     print("🔍 调试信息 - 完整 API 请求体")
    #     print("="*80)
    #     print(f"显示模型名: {model}")
    #     print(f"官方模型名: {official_model}")
    #     print(f"API 端点: {base_url}")
    #     print("\n请求体 JSON:")
    #     print(json.dumps(body, indent=2, ensure_ascii=False))
    #     print("="*80 + "\n")
    #     
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            # 调试日志
            mode = "图生图" if reference_images_base64 else "文生图"
            num_refs = len(reference_images_base64) if reference_images_base64 else 0
            logger.debug(f"正在生成图片... ({mode}, 参考图{num_refs}张, 尝试 {attempt + 1}/{max_retries})")
            logger.debug(f"Model: {model}, Aspect: {aspect_ratio}, Size: {image_size}, Seed: {seed}")
            logger.debug(f"Prompt: {prompt[:100]}...")
            
            response = requests.post(
                base_url,
                headers=headers,
                json=body,
                timeout=120  # Increased timeout for image generation
            )
            
            # Check if request was successful
            logger.debug(f"API 响应已接收，状态码: {response.status_code}")
            if response.status_code == 200:
                logger.debug("API 调用成功")
                response_json = response.json()
                
    #                 # === DEBUG: Print response structure ===
    #                 print("\n" + "="*80)
    #                 print("🔍 调试信息 - API 响应结构")
    #                 print("="*80)
    #                 print(f"响应键: {list(response_json.keys())}")
    #                 if 'candidates' in response_json and len(response_json['candidates']) > 0:
    #                     candidate = response_json['candidates'][0]
    #                     print(f"候选项键: {list(candidate.keys())}")
    #                     if 'content' in candidate:
    #                         print(f"内容键: {list(candidate['content'].keys())}")
    #                         if 'parts' in candidate['content']:
    #                             parts = candidate['content']['parts']
    #                             print(f"Parts 数量: {len(parts)}")
    #                             for i, part in enumerate(parts):
    #                                 print(f"Part {i} 键: {list(part.keys())}")
    #                                 if 'text' in part:
    #                                     print(f"Part {i} text: {part['text'][:200]}")
    #                 print("="*80 + "\n")
    #                 
                return response_json
            else:
                error_msg = f"❌ API 错误 (状态码 {response.status_code})\n详情: {response.text[:200]}"
                logger.error(f"API error: {response.status_code} - {response.text}")
                
                # Don't retry for client errors (4xx)
                if 400 <= response.status_code < 500:
                    if response.status_code == 401:
                        raise Exception("❌ API 密钥无效或已过期，请检查您的密钥")
                    elif response.status_code == 429:
                        raise Exception("❌ 请求过于频繁，请稍后再试")
                    else:
                        raise Exception(error_msg)
                
                # Retry for server errors (5xx)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"服务器错误，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    raise Exception(error_msg)
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {str(e)}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"网络错误，{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                raise Exception(f"网络错误: {str(e)}")
    
    raise Exception("已达最大重试次数，请求失败")


def extract_image_from_gemini_response(response_data):
    """
    Extract image data from Gemini API response
    
    Supports two formats:
    1. Official Gemini format with inline_data (base64):
       {
         "candidates": [{
           "content": {
             "parts": [{
               "inline_data": {
                 "mime_type": "image/png",
                 "data": "base64_string"
               }
             }]
           }
         }]
       }
    
    2. New API platform format with URL in text:
       {
         "candidates": [{
           "content": {
             "parts": [{
               "text": "![image](https://files.closeai.fans/...)"
             }]
           }
         }]
       }
    
    Args:
        response_data (dict): Gemini API response
        
    Returns:
        PIL.Image: Extracted image
    """
    try:
        # 🔍 输出完整的 API 返回内容
    #   print("\n" + "="*80)
    #   print("🔍 官方 API 完整返回内容 (JSON 格式)")
    #   print("="*80)
    #   import json
    #   print(json.dumps(response_data, indent=2, ensure_ascii=False))
    #   print("="*80 + "\n")
    #         
        # Navigate the response structure
        if 'candidates' not in response_data or len(response_data['candidates']) == 0:
            raise Exception("No candidates in API response")
        
        candidate = response_data['candidates'][0]
        
        if 'content' not in candidate or 'parts' not in candidate['content']:
            raise Exception("Invalid response structure")
        
        parts = candidate['content']['parts']
        
        # Try to find inline_data (official Gemini format) first
        for part in parts:
            if 'inline_data' in part or 'inlineData' in part:
                inline_data = part.get('inline_data') or part.get('inlineData')
                
                # 处理两种格式：
                # 1. 标准格式: {"mime_type": "...", "data": "base64..."}
                # 2. SVIP格式: 直接是 base64 字符串
                if isinstance(inline_data, dict):
                    # 标准 Gemini 格式
                    base64_data = inline_data.get('data')
                    if base64_data:
                        logger.debug("Found inline_data (standard Gemini format with dict)")
                        return decode_base64_image(base64_data)
                elif isinstance(inline_data, str):
                    # SVIP 格式：直接是 base64 字符串
                    logger.debug("Found inline_data (SVIP format with direct base64 string)")
                    return decode_base64_image(inline_data)
        
        # If no inline_data, try to extract URL from text (New API format)
        for part in parts:
            if 'text' in part:
                text = part['text']
                logger.debug(f"Checking text field for image URL...")
                
                # Extract URL from markdown format: ![image](URL)
                import re
                markdown_match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', text)
                if markdown_match:
                    url = markdown_match.group(1)
                    print(f"正在下载图片...")
                    logger.debug(f"URL: {url}")
                    return download_image_from_url(url)
                
                # Try to find plain HTTP URL
                url_match = re.search(r'(https?://[^\s\)]+\.(?:png|jpg|jpeg|webp|gif))', text, re.IGNORECASE)
                if url_match:
                    url = url_match.group(1)
                    print(f"正在下载图片...")
                    logger.debug(f"URL: {url}")
                    return download_image_from_url(url)
        
        # If we get here, no image data was found
        raise Exception("No image data found in response (neither inline_data nor URL)")
        
    except Exception as e:
        logger.error(f"Failed to extract image from response: {str(e)}")
        raise


def decode_base64_image(base64_string):
    """
    Decode base64 string to PIL Image
    
    Args:
        base64_string (str): Base64 encoded image string
        
    Returns:
        PIL.Image: Decoded image
    """
    try:
        logger.debug("Decoding base64 image...")
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data))
        # print(f"图片解码成功: {image.size[0]}x{image.size[1]}")
        return image
    except Exception as e:
        logger.error(f"Failed to decode base64 image: {str(e)}")
        raise


def download_image_from_url(url):
    """
    Download image from URL and convert to PIL Image
    
    Args:
        url (str): URL of the image
        
    Returns:
        PIL.Image: Downloaded image
    """
    try:
        logger.debug(f"Downloading from: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        image = Image.open(io.BytesIO(response.content))
        # print(f"图片下载成功: {image.size[0]}x{image.size[1]}")
        return image
    except Exception as e:
        logger.error(f"Failed to download image: {str(e)}")
        raise


def pil_to_comfy_image(pil_image):
    """
    Convert PIL Image to ComfyUI IMAGE tensor format
    
    Args:
        pil_image (PIL.Image): PIL Image object
        
    Returns:
        torch.Tensor: Image in ComfyUI format (1, H, W, C) with values in [0, 1]
    """
    # Convert to RGB if necessary
    if pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')
    
    # Convert to numpy array
    np_image = np.array(pil_image).astype(np.float32) / 255.0
    
    # Add batch dimension and convert to torch tensor
    tensor_image = torch.from_numpy(np_image)[None,]
    
    logger.debug(f"Converted to ComfyUI tensor: {tensor_image.shape}")
    return tensor_image


def comfy_image_to_base64(image_tensor):
    """
    Convert ComfyUI IMAGE tensor to base64 string (without data URI prefix)
    
    Args:
        image_tensor (torch.Tensor): ComfyUI IMAGE tensor (B, H, W, C) with values in [0, 1]
        
    Returns:
        str: Base64 encoded PNG image (raw base64, no prefix)
    """
    # Remove batch dimension and convert to numpy
    np_image = (image_tensor.squeeze(0).numpy() * 255).astype(np.uint8)
    
    # Convert to PIL Image
    pil_image = Image.fromarray(np_image)
    
    # Convert to base64
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    base64_string = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    logger.debug(f"Converted tensor to base64 (size: {pil_image.size})")
    return base64_string


def process_api_response(response_data):
    """
    Process Gemini API response and return PIL Image
    
    Args:
        response_data (dict): Gemini API response data
        
    Returns:
        PIL.Image: Generated image
    """
    try:
        return extract_image_from_gemini_response(response_data)
    except Exception as e:
        logger.error(f"Failed to process API response: {str(e)}")
        raise


def load_images_from_folder(folder_path, file_pattern="*.png,*.jpg,*.jpeg"):
    """
    从文件夹加载图片
    
    Args:
        folder_path (str): 文件夹路径
        file_pattern (str): 文件过滤模式，逗号分隔（如 "*.png,*.jpg,*.jpeg"）
        
    Returns:
        tuple: (PIL Image对象列表, 文件名列表)
    """
    if not os.path.exists(folder_path):
        raise ValueError(f"文件夹不存在: {folder_path}")
    
    if not os.path.isdir(folder_path):
        raise ValueError(f"路径不是文件夹: {folder_path}")
    
    # 解析文件模式
    patterns = [p.strip() for p in file_pattern.split(',')]
    
    # 收集所有匹配的文件
    image_files = []
    for pattern in patterns:
        matching_files = glob.glob(os.path.join(folder_path, pattern))
        image_files.extend(matching_files)
    
    # 去重并排序
    image_files = sorted(set(image_files))
    
    if len(image_files) == 0:
        logger.warning(f"在文件夹 {folder_path} 中未找到匹配 {file_pattern} 的文件")
        return [], []
    
    # 加载图片
    images = []
    filenames = []
    failed_files = []
    
    for file_path in image_files:
        try:
            img = Image.open(file_path)
            # 转换为RGB（如果需要）
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
            filenames.append(os.path.basename(file_path))
            logger.debug(f"已加载: {os.path.basename(file_path)}")
        except Exception as e:
            failed_files.append(os.path.basename(file_path))
            logger.error(f"无法加载图片 {os.path.basename(file_path)}: {str(e)}")
    
    if failed_files:
        logger.warning(f"加载失败的文件: {', '.join(failed_files)}")
    
    logger.info(f"成功加载 {len(images)}/{len(image_files)} 张图片")
    
    return images, filenames


def save_image_to_folder(pil_image, output_folder, filename):
    """
    保存PIL图片到文件夹
    
    Args:
        pil_image (PIL.Image): PIL图片对象
        output_folder (str): 输出文件夹路径
        filename (str): 文件名（保持原文件名）
        
    Returns:
        str: 保存的文件路径
    """
    if not output_folder:
        raise ValueError("输出文件夹路径不能为空")
    
    # 创建输出文件夹（如果不存在）
    os.makedirs(output_folder, exist_ok=True)
    
    # 构建完整路径
    output_path = os.path.join(output_folder, filename)
    
    # 保存图片
    try:
        pil_image.save(output_path, quality=95)
        logger.debug(f"已保存: {filename}")
        return output_path
    except Exception as e:
        logger.error(f"保存图片失败 {filename}: {str(e)}")
        raise
