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


def parse_api_error(status_code, error_text):
    """
    解析 API 错误，返回用户友好的错误消息
    
    Args:
        status_code (int): HTTP 状态码
        error_text (str): 原始错误文本
        
    Returns:
        str: 用户友好的错误消息
    """
    # 检测是否为 HTML 响应（Cloudflare 等网关错误）
    is_html = error_text.strip().startswith('<!DOCTYPE') or error_text.strip().startswith('<html')
    
    # 常见错误码的友好提示
    error_messages = {
        500: "服务器内部错误，请稍后重试",
        502: "网关错误，服务器暂时不可用",
        503: "服务暂时不可用，可能正在维护中",
        504: "网关超时，服务器响应时间过长",
        520: "服务器返回未知错误",
        521: "服务器已下线",
        522: "连接超时",
        523: "源站不可达",
        524: "发生超时",
    }
    
    if status_code in error_messages:
        base_msg = error_messages[status_code]
        if is_html:
            return f"⚠️ {base_msg} (错误码: {status_code})"
        else:
            # 如果不是 HTML，可以显示部分错误信息
            short_error = error_text[:100] if len(error_text) > 100 else error_text
            return f"⚠️ {base_msg}\n   详情: {short_error}"
    
    # 其他错误
    if is_html:
        return f"⚠️ 服务器错误 (错误码: {status_code})"
    else:
        short_error = error_text[:200] if len(error_text) > 200 else error_text
        return f"⚠️ API 错误 (状态码 {status_code}): {short_error}"

# Model name mapping: UI name -> Official API name
# This allows user-friendly names in the interface while using official names for API calls
MODEL_NAME_MAPPING = {
    "nano-banana-svip": "nano-banana-svip",
    "nano-banana-pro-svip": "nano-banana-pro-svip",
}

# 新模型列表 (使用 OpenAI 格式 API)
# 这些模型通过 New API 后台映射到实际的 Gemini 3 Pro Image Preview 模型
OPENAI_FORMAT_MODELS = ["nano-banana-pro-default"]

# 宽高比 -> 1K 分辨率映射表 (来自 Gemini 3 Pro Image 官方文档)
# 用于 OpenAI 格式 API 的 size 参数
ASPECT_RATIO_TO_1K_SIZE = {
    "1:1":  "1024x1024",
    "2:3":  "848x1264",
    "3:2":  "1264x848",
    "3:4":  "896x1200",
    "4:3":  "1200x896",
    "4:5":  "928x1152",
    "5:4":  "1152x928",
    "9:16": "768x1376",
    "16:9": "1376x768",
    "21:9": "1584x672",
}

# image_size -> 模型后缀映射
# 根据用户选择的清晰度，选择对应的模型版本
IMAGE_SIZE_TO_MODEL_SUFFIX = {
    "1K": "-1K",
    "2K": "-2K",
    "4K": "-4K",
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


def is_openai_format_model(model):
    """
    检查模型是否使用 OpenAI 格式 API
    
    Args:
        model (str): 模型名称
        
    Returns:
        bool: True 如果使用 OpenAI 格式
    """
    return model in OPENAI_FORMAT_MODELS


def get_openai_model_and_size(model, aspect_ratio, image_size):
    """
    根据用户选择的模型、宽高比和清晰度，获取实际的 OpenAI API 模型名和尺寸
    
    Args:
        model (str): 用户选择的模型 (如 "nano-banana-pro-default")
        aspect_ratio (str): 宽高比 (如 "16:9")
        image_size (str): 清晰度 (如 "2K")
        
    Returns:
        tuple: (实际模型名, 1K分辨率尺寸)
    """
    # 获取 1K 分辨率尺寸
    size = ASPECT_RATIO_TO_1K_SIZE.get(aspect_ratio, "1024x1024")
    
    # 根据 image_size 选择对应的模型版本
    suffix = IMAGE_SIZE_TO_MODEL_SUFFIX.get(image_size, "-1K")
    actual_model = model + suffix
    
    return actual_model, size


def call_openai_format_api(
    prompt,
    model,
    size,
    api_key,
    reference_images_base64=None,
    max_retries=3,
    response_format="url"
):
    """
    调用 OpenAI 格式的图片生成/编辑 API
    
    Args:
        prompt (str): 提示词
        model (str): 模型名称 (如 "nano-banana-pro-default-2K")
        size (str): 图片尺寸 (如 "1376x768")
        api_key (str): API 密钥
        reference_images_base64 (list): 参考图的 base64 数据列表（图生图时使用，支持多张）
        max_retries (int): 最大重试次数
        response_format (str): 返回格式 "url" 或 "b64_json"
        
    Returns:
        PIL.Image: 生成的图片
    """
    if not api_key:
        raise ValueError("API key is required")
    
    base_url = "https://o1key.com"
    
    # 根据是否有参考图选择接口
    if reference_images_base64 and len(reference_images_base64) > 0:
        # 图生图：使用 /v1/images/edits (multipart/form-data)
        endpoint = f"{base_url}/v1/images/edits"
        return _call_openai_image_edit(endpoint, prompt, model, size, api_key, reference_images_base64, max_retries, response_format)
    else:
        # 文生图：使用 /v1/images/generations (JSON)
        endpoint = f"{base_url}/v1/images/generations"
        return _call_openai_image_generation(endpoint, prompt, model, size, api_key, max_retries, response_format)


def _call_openai_image_generation(endpoint, prompt, model, size, api_key, max_retries, response_format="url"):
    """
    调用 OpenAI 格式的文生图 API (/v1/images/generations)
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": response_format,
    }
    
    logger.debug(f"OpenAI API request: {endpoint}, model={model}, size={size}")
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=body,
                timeout=120
            )
            
            if response.status_code == 200:
                response_json = response.json()
                return _parse_openai_response(response_json)
            else:
                error_text = response.text
                friendly_error = parse_api_error(response.status_code, error_text)
                logger.error(f"API 错误 (状态码 {response.status_code})")
                
                # 检测 API 分组不匹配的错误
                if "model_not_found" in error_text and "无可用渠道" in error_text:
                    import re
                    group_match = re.search(r'分组\s*(\w+)\s*下', error_text)
                    group_name = group_match.group(1) if group_match else "default"
                    
                    friendly_msg = (
                        f"❌ API Key 与模型不匹配\n\n"
                        f"您当前使用的 API Key 属于「{group_name}」分组，\n"
                        f"但您选择的模型「{model}」需要使用其他分组的 API Key。\n\n"
                        f"💡 解决方法：\n"
                        f"   • 请确认您的 API Key 分组与所选模型匹配\n"
                        f"   • 或者更换为对应分组的 API Key"
                    )
                    raise Exception(friendly_msg)
                
                if 400 <= response.status_code < 500:
                    if response.status_code == 401:
                        raise Exception("❌ API 密钥无效或已过期")
                    elif response.status_code == 429:
                        raise Exception("❌ 请求过于频繁，请稍后再试")
                    else:
                        raise Exception(f"❌ {friendly_error}")
                
                # 5xx 服务器错误，重试
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"{friendly_error}")
                    print(f"⏳ {wait_time}秒后自动重试...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"❌ {friendly_error}\n💡 建议稍后重试或降低图片清晰度")
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⚠️ 网络错误，{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                raise Exception(f"❌ 网络错误: {str(e)}")
    
    raise Exception("已达最大重试次数，请求失败")


def _call_openai_image_edit(endpoint, prompt, model, size, api_key, images_base64, max_retries, response_format="url"):
    """
    调用 OpenAI 格式的图生图 API (/v1/images/edits)
    使用 multipart/form-data 格式，支持多张参考图
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    # 构建多图上传的 files 列表
    # multipart/form-data 支持同名字段传递多个文件
    files = []
    for idx, img_base64 in enumerate(images_base64):
        image_bytes = base64.b64decode(img_base64)
        files.append(("image", (f"image_{idx}.png", image_bytes, "image/png")))
    
    data = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": response_format,
    }
    
    logger.debug(f"OpenAI Edit API request: {endpoint}, model={model}, size={size}, images={len(images_base64)}")
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                files=files,
                data=data,
                timeout=180
            )
            
            if response.status_code == 200:
                response_json = response.json()
                return _parse_openai_response(response_json)
            else:
                error_text = response.text
                friendly_error = parse_api_error(response.status_code, error_text)
                logger.error(f"API 错误 (状态码 {response.status_code})")
                
                # 检测 API 分组不匹配的错误
                if "model_not_found" in error_text and "无可用渠道" in error_text:
                    import re
                    group_match = re.search(r'分组\s*(\w+)\s*下', error_text)
                    group_name = group_match.group(1) if group_match else "default"
                    
                    friendly_msg = (
                        f"❌ API Key 与模型不匹配\n\n"
                        f"您当前使用的 API Key 属于「{group_name}」分组，\n"
                        f"但您选择的模型「{model}」需要使用其他分组的 API Key。\n\n"
                        f"💡 解决方法：\n"
                        f"   • 请确认您的 API Key 分组与所选模型匹配\n"
                        f"   • 或者更换为对应分组的 API Key"
                    )
                    raise Exception(friendly_msg)
                
                if 400 <= response.status_code < 500:
                    if response.status_code == 401:
                        raise Exception("❌ API 密钥无效或已过期")
                    elif response.status_code == 429:
                        raise Exception("❌ 请求过于频繁，请稍后再试")
                    else:
                        raise Exception(f"❌ {friendly_error}")
                
                # 5xx 服务器错误，重试
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"{friendly_error}")
                    print(f"⏳ {wait_time}秒后自动重试...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"❌ {friendly_error}\n💡 建议稍后重试或降低图片清晰度")
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⚠️ 网络错误，{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                raise Exception(f"❌ 网络错误: {str(e)}")
    
    raise Exception("已达最大重试次数，请求失败")


def _parse_openai_response(response_json):
    """
    解析 OpenAI 格式 API 的响应，返回 PIL.Image
    """
    try:
        if "data" not in response_json or len(response_json["data"]) == 0:
            raise Exception(f"响应中没有图片数据: {list(response_json.keys())}")
        
        image_data = response_json["data"][0]
        
        if "b64_json" in image_data:
            base64_str = image_data["b64_json"]
            return decode_base64_image(base64_str)
        
        if "url" in image_data:
            url = image_data["url"]
            return download_image_from_url(url)
        
        available_keys = list(image_data.keys())
        raise Exception(f"无法解析图片数据，可用字段: {available_keys}")
        
    except Exception as e:
        logger.error(f"Failed to parse OpenAI response: {str(e)}")
        raise


def call_nano_banana_api(
    prompt,
    model="nano-banana-pro-svip",
    aspect_ratio="1:1",
    image_size=None,
    seed=None,
    api_key=None,
    reference_images_base64=None,  # 支持多个参考图（列表）
    max_retries=3,
    response_format="url"
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
        response_format (str): Response format "url" or "b64_json"
        
    Returns:
        dict: API response containing the generated image
               或 PIL.Image (当使用 OpenAI 格式时)
    """
    if not api_key:
        raise ValueError("API key is required")
    
    # ========== 路由判断：OpenAI 格式 vs Gemini 格式 ==========
    if is_openai_format_model(model):
        # 使用 OpenAI 格式 API
        actual_model, size = get_openai_model_and_size(model, aspect_ratio, image_size or "1K")
        logger.debug(f"Using OpenAI format: model={actual_model}, size={size}, response_format={response_format}")
        
        # 直接返回 PIL.Image（与 Gemini 格式的返回值不同）
        pil_image = call_openai_format_api(
            prompt=prompt,
            model=actual_model,
            size=size,
            api_key=api_key,
            reference_images_base64=reference_images_base64,  # 支持多张参考图
            max_retries=max_retries,
            response_format=response_format
        )
        
        # 包装成与 Gemini 格式兼容的响应结构
        # 这样 process_api_response 可以统一处理
        return {"_openai_pil_image": pil_image}
    
    # ========== 原有逻辑：Gemini 格式 API ==========
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
                # 解析错误响应，检测特定错误类型
                error_text = response.text
                friendly_error = parse_api_error(response.status_code, error_text)
                logger.error(f"API error: {response.status_code}")
                
                # 检测 API 分组不匹配的错误（用户使用了错误的 API Key）
                if "model_not_found" in error_text and "无可用渠道" in error_text:
                    # 提取分组名称用于提示
                    import re
                    group_match = re.search(r'分组\s*(\w+)\s*下', error_text)
                    group_name = group_match.group(1) if group_match else "default"
                    
                    friendly_msg = (
                        f"❌ API Key 与模型不匹配\n\n"
                        f"您当前使用的 API Key 属于「{group_name}」分组，\n"
                        f"但您选择的模型「{model}」需要使用「svip」分组的 API Key。\n\n"
                        f"💡 解决方法：\n"
                        f"   • 如果您要使用 svip 模型，请更换为 svip 专用的 API Key\n"
                        f"   • 如果您只有 default 分组的 Key，请将模型改为「nano-banana-pro-default」"
                    )
                    raise Exception(friendly_msg)
                
                # Don't retry for client errors (4xx)
                if 400 <= response.status_code < 500:
                    if response.status_code == 401:
                        raise Exception("❌ API 密钥无效或已过期，请检查您的密钥")
                    elif response.status_code == 429:
                        raise Exception("❌ 请求过于频繁，请稍后再试")
                    else:
                        raise Exception(f"❌ {friendly_error}")
                
                # Retry for server errors (5xx)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"{friendly_error}")
                    print(f"⏳ {wait_time}秒后自动重试...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"❌ {friendly_error}\n💡 建议稍后重试或降低图片清晰度")
                    
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
        # Navigate the response structure
        if 'candidates' not in response_data or len(response_data['candidates']) == 0:
            # 打印调试信息帮助诊断
            import json
            print("\n" + "="*60)
            print("❌ API 响应结构异常 - 调试信息")
            print("="*60)
            print(f"响应键: {list(response_data.keys())}")
            # 限制输出长度，避免刷屏
            response_str = json.dumps(response_data, indent=2, ensure_ascii=False)
            if len(response_str) > 1000:
                response_str = response_str[:1000] + "\n... (输出已截断)"
            print(response_str)
            print("="*60 + "\n")
            raise Exception("No candidates in API response")
        
        candidate = response_data['candidates'][0]
        
        if 'content' not in candidate or 'parts' not in candidate['content']:
            # 打印调试信息帮助诊断
            import json
            print("\n" + "="*60)
            print("❌ API 响应结构异常 - 调试信息")
            print("="*60)
            print(f"候选项键: {list(candidate.keys())}")
            candidate_str = json.dumps(candidate, indent=2, ensure_ascii=False)
            if len(candidate_str) > 1000:
                candidate_str = candidate_str[:1000] + "\n... (输出已截断)"
            print(candidate_str)
            print("="*60 + "\n")
            raise Exception("Invalid response structure: missing content or parts")
        
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
    
    处理常见的 Base64 格式问题：
    1. 移除 data URI 前缀 (如 "data:image/png;base64,")
    2. 添加缺失的填充字符 (=)
    
    Args:
        base64_string (str): Base64 encoded image string
        
    Returns:
        PIL.Image: Decoded image
    """
    try:
        logger.debug("Decoding base64 image...")
        
        # 1. 移除 data URI 前缀 (如果存在)
        if base64_string.startswith('data:'):
            # 格式: data:image/png;base64,xxxxx
            comma_idx = base64_string.find(',')
            if comma_idx != -1:
                base64_string = base64_string[comma_idx + 1:]
                logger.debug("Removed data URI prefix")
        
        # 2. 移除可能的空白字符
        base64_string = base64_string.strip()
        
        # 3. 修复 Base64 填充问题
        # Base64 字符串长度必须是 4 的倍数，不足的用 '=' 填充
        padding_needed = len(base64_string) % 4
        if padding_needed:
            base64_string += '=' * (4 - padding_needed)
            logger.debug(f"Added {4 - padding_needed} padding characters")
        
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
    Process API response and return PIL Image
    
    支持两种格式:
    1. Gemini 格式 - 从 candidates/content/parts 中提取图片
    2. OpenAI 格式 - 直接从包装的 _openai_pil_image 字段获取
    
    Args:
        response_data (dict): API response data
        
    Returns:
        PIL.Image: Generated image
    """
    try:
        # 检查是否是 OpenAI 格式的包装响应
        if "_openai_pil_image" in response_data:
            return response_data["_openai_pil_image"]
        
        # 原有逻辑：处理 Gemini 格式
        return extract_image_from_gemini_response(response_data)
    except Exception as e:
        logger.error(f"Failed to process API response: {str(e)}")
        raise


def format_time(seconds):
    """将秒数格式化为可读时间"""
    if seconds is None:
        return "未知"
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}分{secs}秒"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}小时{mins}分"


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
    保存PIL图片到文件夹（自动重命名避免覆盖）
    
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
    
    # 防覆盖：如果文件已存在，自动添加 _1, _2, _3... 后缀
    if os.path.exists(output_path):
        # 拆分文件名和扩展名
        name, ext = os.path.splitext(filename)
        counter = 1
        
        # 寻找可用的文件名
        while True:
            new_filename = f"{name}_{counter}{ext}"
            output_path = os.path.join(output_folder, new_filename)
            if not os.path.exists(output_path):
                logger.debug(f"文件已存在，重命名: {filename} -> {new_filename}")
                break
            counter += 1
    
    # 保存图片
    try:
        pil_image.save(output_path, quality=95)
        saved_filename = os.path.basename(output_path)
        logger.debug(f"已保存: {saved_filename}")
        return output_path
    except Exception as e:
        logger.error(f"保存图片失败 {filename}: {str(e)}")
        raise
