"""
Utility functions for Gemini Nano Banana API integration
Uses official Gemini API format for full compatibility
"""
import requests
import base64
import io
import json
import numpy as np
import torch
from PIL import Image
import time
import logging
import os
import glob
from pathlib import Path

# 禁用 SSL 警告（Origin Certificate 是自签名证书，这是正常的）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# API 基础地址配置（由配置节点提供）
# ============================================================
API_BASE_URL = "https://api.o1key.com"  # 默认地址
# ============================================================

# ============================================================
# 代理配置 (加速下载)
# ============================================================
# 设置为 None 表示不使用代理
# 设置为代理地址启用代理，例如:
#   "http://127.0.0.1:10808"  (HTTP 代理)
#   "socks5://127.0.0.1:10808" (SOCKS5 代理)

# PROXY_URL = "http://127.0.0.1:10808"  # 你的本地代理
PROXY_URL = None  # 不使用代理（测试直连新加坡）

# 构建 proxies 字典
PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
# ============================================================


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


def format_json_for_display(data, max_base64_length=100):
    """
    格式化 JSON 数据用于显示，截断过长的 base64 数据
    
    Args:
        data: JSON 数据（dict 或已解析的 JSON）
        max_base64_length: base64 字符串显示的最大长度
        
    Returns:
        str: 格式化后的 JSON 字符串
    """
    def truncate_base64(obj):
        """递归处理对象，截断 base64 字符串"""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key == 'data' and isinstance(value, str) and len(value) > max_base64_length:
                    # 截断 base64 数据
                    result[key] = value[:max_base64_length] + f"... [已截断，总长度: {len(value)} 字符]"
                elif key == 'inline_data' or key == 'inlineData':
                    # 处理 inline_data 对象
                    if isinstance(value, dict) and 'data' in value:
                        if isinstance(value['data'], str) and len(value['data']) > max_base64_length:
                            value_copy = value.copy()
                            value_copy['data'] = value['data'][:max_base64_length] + f"... [已截断，总长度: {len(value['data'])} 字符]"
                            result[key] = value_copy
                        else:
                            result[key] = truncate_base64(value)
                    else:
                        result[key] = truncate_base64(value)
                else:
                    result[key] = truncate_base64(value)
            return result
        elif isinstance(obj, list):
            return [truncate_base64(item) for item in obj]
        elif isinstance(obj, str) and len(obj) > max_base64_length * 10:
            # 检查是否是 base64 字符串（很长且只包含 base64 字符）
            if all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in obj[:100]):
                return obj[:max_base64_length] + f"... [已截断，总长度: {len(obj)} 字符]"
        return obj
    
    try:
        if isinstance(data, str):
            data = json.loads(data)
        truncated_data = truncate_base64(data)
        return json.dumps(truncated_data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"格式化失败: {str(e)}\n原始数据: {str(data)[:500]}"


# Model name mapping: UI name -> Official API name
MODEL_NAME_MAPPING = {
    "gemini-3-pro-image-preview-url": "gemini-3-pro-image-preview-url"
}

# 当前支持的模型（固定为单一模型）
CURRENT_MODEL = "gemini-3-pro-image-preview-url"

# 该模型使用 Gemini 原生格式，返回 URL 格式
# 支持 1K/2K/4K 三种清晰度

# Gemini 模型分类
# URL 格式模型：返回图片 URL，需要额外下载
GEMINI_URL_MODELS = [
    "gemini-3-pro-image-preview-url",
    # 注意：带清晰度后缀的模型会动态生成，不需要在此列表中
]

# Base64 格式模型：直接返回 base64 编码的图片数据
GEMINI_B64_MODELS = [
    # 如果有返回 base64 的模型，在此添加
]

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
        display_name (str): User-friendly name
        
    Returns:
        str: Official API name
    """
    return MODEL_NAME_MAPPING.get(display_name, display_name)


def is_openai_format_model(model, network_url=None):
    """
    检查模型是否使用 OpenAI 格式 API
    
    Args:
        model (str): 模型名称
        network_url (str): 网络线路URL（保留参数以保持兼容性）
        
    Returns:
        bool: True 如果使用 OpenAI 格式
    """
    # gemini-3-pro-image-preview-url 系列使用 Gemini 原生格式
    # 所有线路（包括加速线路）都使用同样的接口格式：/v1beta/models/{model}:generateContent
    # 只是 base URL 不同
    if "gemini" in model.lower():
        return False
    
    # 其他模型使用 OpenAI 格式
    return True


def get_openai_model_and_size(model, aspect_ratio, image_size):
    """
    根据用户选择的模型、宽高比和清晰度，获取实际的 OpenAI API 模型名和尺寸
    
    Args:
        model (str): 用户选择的模型 (如 "gemini-3-pro-image-preview-url")
        aspect_ratio (str): 宽高比 (如 "16:9")
        image_size (str): 清晰度 (如 "2K")
        
    Returns:
        tuple: (实际模型名, 1K分辨率尺寸)
    """
    # 获取 1K 分辨率尺寸
    size = ASPECT_RATIO_TO_1K_SIZE.get(aspect_ratio, "1024x1024")
    
    # 根据 image_size 动态生成模型名
    base_model = "gemini-3-pro-image-preview"
    
    if image_size == "1K" or image_size is None:
        # 1K 是默认的
        actual_model = f"{base_model}-url"
    else:
        # 2K 或 4K，在 -url 前插入尺寸
        size_lower = image_size.lower()  # 2K -> 2k, 4K -> 4k
        actual_model = f"{base_model}-{size_lower}-url"
    
    return actual_model, size


def call_openai_format_api(
    prompt,
    model,
    size,
    api_key,
    reference_images_base64=None,
    response_format=None,  # None表示自动适配
    network_url=None,  # 网络线路URL，从配置节点传入
    proxy=""  # 代理设置
):
    """
    调用 OpenAI 格式的图片生成/编辑 API
    
    Args:
        prompt (str): 提示词
        model (str): 模型名称
        size (str): 图片尺寸 (如 "1376x768")
        api_key (str): API 密钥
        reference_images_base64 (list): 参考图的 base64 数据列表（图生图时使用，支持多张）
        response_format (str): 返回格式，None表示自动选择
        
    Returns:
        PIL.Image: 生成的图片
    """
    if not api_key:
        raise ValueError("API密钥不能为空")
    
    # 自动适配 response_format：默认使用 url 格式
    if response_format is None:
        response_format = "url"
    
    # 使用配置节点传入的network_url，如果没有则使用全局配置
    base_url = network_url if network_url else API_BASE_URL
    
    # 根据是否有参考图选择接口
    if reference_images_base64 and len(reference_images_base64) > 0:
        # 图生图：使用 /v1/images/edits (multipart/form-data)
        endpoint = f"{base_url}/v1/images/edits"
        return _call_openai_image_edit(endpoint, prompt, model, size, api_key, reference_images_base64, response_format, proxy)
    else:
        # 文生图：使用 /v1/images/generations (JSON)
        endpoint = f"{base_url}/v1/images/generations"
        return _call_openai_image_generation(endpoint, prompt, model, size, api_key, response_format, proxy)


def _call_openai_image_generation(endpoint, prompt, model, size, api_key, response_format=None, proxy=""):
    """
    调用图片生成 API
    
    注意：已禁用自动重试机制，避免因 504 等超时错误导致重复扣费
    """
    # 自动适配 response_format
    if response_format is None:
        response_format = "url"
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
    
    logger.debug(f"发送图片生成请求")
    
    # 构建代理配置
    user_proxy = proxy.strip() if proxy else None
    active_proxy = user_proxy or PROXY_URL
    proxies_dict = {"http": active_proxy, "https": active_proxy} if active_proxy else None
    
    # 根据是否使用代理调整超时时间
    if active_proxy:
        connect_timeout = 120
        read_timeout = 600
    else:
        connect_timeout = 60
        read_timeout = 600
    
    # 简化日志输出
    print(f"\n⏱️ 发送请求...", flush=True)
    if active_proxy:
        print(f"    🔀 代理: 已启用", flush=True)
    else:
        print(f"    🔀 代理: 未启用（直连）", flush=True)
    
    _t_request = time.time()
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=body,
            timeout=(connect_timeout, read_timeout),
            verify=False,  # 禁用 SSL 验证（Origin Certificate 是自签名证书）
            proxies=proxies_dict
        )
        _t_connect = time.time() - _t_request
        
        # 确认代理使用情况并显示连接建立
        if active_proxy:
            via_header = response.headers.get('Via', '')
            if via_header:
                print(f"    ✅ 代理已生效, 连接建立: {_t_connect:.2f}s", flush=True)
            else:
                print(f"    ✅ 代理已应用, 连接建立: {_t_connect:.2f}s", flush=True)
        else:
            print(f"    ✅ 连接建立: {_t_connect:.2f}s", flush=True)
        
        if response.status_code == 200:
            try:
                _t_response = time.time()
                response_json = response.json()
                _t_parse = time.time() - _t_response
                
                # 只显示总耗时
                total_time = _t_connect + _t_parse
                print(f"    ⏱️  总耗时: {total_time:.3f}s", flush=True)
                
                return _parse_openai_response(response_json)
            except json.JSONDecodeError:
                logger.warning("响应不是有效的 JSON 格式")
                raise Exception("API 返回了非 JSON 格式的响应")
        else:
            error_text = response.text
            friendly_error = parse_api_error(response.status_code, error_text)
            logger.error(f"请求错误 (状态码 {response.status_code})")
            
            # 检测模型未配置的错误
            if "model_not_found" in error_text or "无可用渠道" in error_text:
                friendly_msg = (
                    f"❌ 模型暂时不可用\n\n"
                    f"当前所选模型暂时无法使用，可能正在维护中。\n\n"
                    f"💡 解决方法：\n"
                    f"   • 请稍后重试\n"
                    f"   • 或联系技术支持获取帮助"
                )
                raise Exception(friendly_msg)
            
            # 客户端错误 (4xx)
            if response.status_code == 401:
                raise Exception("❌ API 密钥无效或已过期")
            elif response.status_code == 429:
                raise Exception("❌ 请求过于频繁，请稍后再试")
            elif response.status_code == 504:
                raise Exception(
                    f"❌ {friendly_error}\n\n"
                    f"💡 提示：\n"
                    f"   • 504 超时可能是因为 4K 图片生成时间较长\n"
                    f"   • 请求可能已在服务端处理中，请稍后检查是否已扣费\n"
                    f"   • 建议先用 2K 测试效果，再生成 4K\n"
                    f"   • 如需重试，请手动重新运行"
                )
            else:
                raise Exception(f"❌ {friendly_error}\n💡 建议稍后手动重试或降低图片清晰度")
                
    except requests.exceptions.Timeout:
        raise Exception(
            "❌ 请求超时\n\n"
            "💡 提示：\n"
            "   • 生成高清图片需要较长时间\n"
            "   • 请求可能已在处理中\n"
            "   • 建议稍后重试，避免重复提交"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {str(e)}")
        raise Exception(f"❌ 网络连接失败\n💡 请检查网络连接后重试")


def _call_openai_image_edit(endpoint, prompt, model, size, api_key, images_base64, response_format=None, proxy=""):
    """
    调用图生图 API
    使用 multipart/form-data 格式，支持多张参考图
    
    注意：已禁用自动重试机制，避免因 504 等超时错误导致重复扣费
    """
    # 自动适配 response_format
    if response_format is None:
        response_format = "url"
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
    
    logger.debug(f"发送图生图请求，参考图数量: {len(images_base64)}")
    
    # 构建代理配置
    user_proxy = proxy.strip() if proxy else None
    active_proxy = user_proxy or PROXY_URL
    proxies_dict = {"http": active_proxy, "https": active_proxy} if active_proxy else None
    
    # 根据是否使用代理调整超时时间
    if active_proxy:
        connect_timeout = 120
        read_timeout = 600
    else:
        connect_timeout = 60
        read_timeout = 600
    
    # 简化日志输出
    print(f"\n⏱️ 发送请求...", flush=True)
    if active_proxy:
        print(f"    🔀 代理: 已启用", flush=True)
    else:
        print(f"    🔀 代理: 未启用（直连）", flush=True)
    
    _t_request = time.time()
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            files=files,
            data=data,
            timeout=(connect_timeout, read_timeout),
            verify=False,  # 禁用 SSL 验证（Origin Certificate 是自签名证书）
            proxies=proxies_dict
        )
        _t_connect = time.time() - _t_request
        
        # 确认代理使用情况并显示连接建立
        if active_proxy:
            via_header = response.headers.get('Via', '')
            if via_header:
                print(f"    ✅ 代理已生效, 连接建立: {_t_connect:.2f}s", flush=True)
            else:
                print(f"    ✅ 代理已应用, 连接建立: {_t_connect:.2f}s", flush=True)
        else:
            print(f"    ✅ 连接建立: {_t_connect:.2f}s", flush=True)
        
        if response.status_code == 200:
            try:
                _t_response = time.time()
                response_json = response.json()
                _t_parse = time.time() - _t_response
                
                # 只显示总耗时
                total_time = _t_connect + _t_parse
                print(f"    ⏱️  总耗时: {total_time:.3f}s", flush=True)
                
                return _parse_openai_response(response_json)
            except json.JSONDecodeError:
                logger.warning("响应不是有效的 JSON 格式")
                raise Exception("API 返回了非 JSON 格式的响应")
        else:
            error_text = response.text
            friendly_error = parse_api_error(response.status_code, error_text)
            logger.error(f"请求错误 (状态码 {response.status_code})")
            
            # 检测模型未配置的错误
            if "model_not_found" in error_text or "无可用渠道" in error_text:
                friendly_msg = (
                    f"❌ 模型暂时不可用\n\n"
                    f"当前所选模型暂时无法使用，可能正在维护中。\n\n"
                    f"💡 解决方法：\n"
                    f"   • 请稍后重试\n"
                    f"   • 或联系技术支持获取帮助"
                )
                raise Exception(friendly_msg)
            
            # 客户端错误 (4xx)
            if response.status_code == 401:
                raise Exception("❌ API 密钥无效或已过期")
            elif response.status_code == 429:
                raise Exception("❌ 请求过于频繁，请稍后再试")
            elif response.status_code == 504:
                raise Exception(
                    f"❌ {friendly_error}\n\n"
                    f"💡 提示：\n"
                    f"   • 504 超时可能是因为 4K 图片生成时间较长\n"
                    f"   • 请求可能已在服务端处理中，请稍后检查是否已扣费\n"
                    f"   • 建议先用 2K 测试效果，再生成 4K\n"
                    f"   • 如需重试，请手动重新运行"
                )
            else:
                raise Exception(f"❌ {friendly_error}\n💡 建议稍后手动重试或降低图片清晰度")
                
    except requests.exceptions.Timeout:
        raise Exception(
            "❌ 请求超时\n\n"
            "💡 提示：\n"
            "   • 生成高清图片需要较长时间\n"
            "   • 请求可能已在处理中\n"
            "   • 建议稍后重试，避免重复提交"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {str(e)}")
        raise Exception(f"❌ 网络连接失败\n💡 请检查网络连接后重试")


def _parse_openai_response(response_json):
    """
    解析 OpenAI 格式 API 的响应，返回 PIL.Image
    """
    try:
        _t_parse = time.time()
        
        if "data" not in response_json or len(response_json["data"]) == 0:
            raise Exception(f"响应中没有图片数据: {list(response_json.keys())}")
        
        image_data = response_json["data"][0]
        
        if "b64_json" in image_data:
            base64_str = image_data["b64_json"]
            print(f"\n⏱️ 正在提取图片数据...", flush=True)
            result = decode_base64_image(base64_str)
            print(f"    ✅ 提取完成: 耗时 {time.time()-_t_parse:.2f}s", flush=True)
            return result
        
        if "url" in image_data:
            url = image_data["url"]
            print(f"\n⏱️ 正在提取图片数据...", flush=True)
            result = download_image_from_url(url)
            print(f"    ✅ 提取完成: 耗时 {time.time()-_t_parse:.2f}s", flush=True)
            return result
        
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
    response_format="url",
    proxy="",  # 用户自定义代理，如 http://127.0.0.1:7890
    network_url=None  # 网络线路URL，从配置节点传入
):
    """
    Call the Gemini Nano Banana API using official Gemini format
    
    注意：已禁用自动重试机制，避免因 504 等超时错误导致重复扣费
    
    Args:
        prompt (str): The text prompt for image generation
        model (str): Model to use (nano-banana-svip or nano-banana-pro-svip)
        aspect_ratio (str): Aspect ratio for the generated image (1:1, 16:9, etc.)
        image_size (str): Image size (1K, 2K, 4K) - only for nano-banana-pro-svip
        seed (int): Random seed for reproducibility (optional)
        api_key (str): API key for authentication
        reference_images_base64 (list): List of base64 encoded reference images for image-to-image
        response_format (str): Response format "url" or "b64_json"
        
    Returns:
        dict: API response containing the generated image
               或 PIL.Image (当使用 OpenAI 格式时)
    """
    if not api_key:
        raise ValueError("API key is required")
    
    # ========== 路由判断：OpenAI 格式 vs Gemini 格式 ==========
    # 根据线路和模型名判断使用哪种接口格式
    if is_openai_format_model(model, network_url):
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
            response_format=response_format,
            network_url=network_url,  # 传递网络线路URL
            proxy=proxy  # 传递代理设置
        )
        
        # 包装成与 Gemini 格式兼容的响应结构
        # 这样 process_api_response 可以统一处理
        return {"_openai_pil_image": pil_image}
    
    # ========== 原有逻辑：Gemini 格式 API ==========
    # 检查模型是否在GEMINI列表中（使用原始模型名，包含A-前缀）
    # 注意：A-前缀只用于UI区分渠道，不影响模型检查
    is_gemini_b64_model = model in GEMINI_B64_MODELS
    if is_gemini_b64_model and response_format == "url":
        # 这些模型默认返回 b64_json，如果用户选择了 url，我们仍然使用 b64_json
        # 因为 Gemini 格式 API 的响应格式是由 API 本身决定的
        response_format = "b64_json"
        logger.debug(f"Model {model} is in GEMINI_B64_MODELS, using b64_json format")
    
    # 检查是否为 Gemini URL 系列模型（已包含尺寸信息的模型）
    # 注意：使用原始模型名（包含A-前缀）进行检查
    is_gemini_url_model = model in GEMINI_URL_MODELS
    
    # Convert user-friendly model name to official API name
    # 注意：在检查完模型列表后，再转换为API模型名（去掉A-前缀）
    official_model = get_official_model_name(model)
    
    # 处理以 -url 结尾的模型（如 A-gemini-3-pro-image-preview-url）
    # 根据 image_size 动态生成实际模型名
    # 平台模型命名规则：
    #   - 1K/默认: gemini-3-pro-image-preview-url (没有 1k)
    #   - 2K: gemini-3-pro-image-preview-2k-url
    #   - 4K: gemini-3-pro-image-preview-4k-url
    # 注意：如果模型已在 GEMINI_URL_MODELS 中（已包含尺寸后缀），则跳过动态添加
    # 注意：这里使用official_model（已去掉A-前缀）进行处理
    if official_model.endswith("-url") and image_size and not is_gemini_url_model:
        if image_size in ["2K", "4K"]:
            base_model = official_model[:-4]  # 去掉 "-url"
            size_lower = image_size.lower()  # 2K -> 2k, 4K -> 4k
            official_model = f"{base_model}-{size_lower}-url"
        # 1K 时保持原名 gemini-3-pro-image-preview-url
    
    logger.debug(f"Model mapping: {model} -> {official_model}")
    
    # 使用配置节点传入的network_url，如果没有则使用全局配置
    active_base_url = network_url if network_url else API_BASE_URL
    
    # Build the API endpoint
    base_url = f"{active_base_url}/v1beta/models/{official_model}:generateContent"
    
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
    
    # 添加 imageSize 参数
    # 根据平台 API 文档，imageSize 使用大写格式: 1K, 2K, 4K
    if image_size:
        image_config["imageSize"] = image_size.upper()
    
    generation_config = {
        "imageConfig": image_config
    }
    
    # 对于 Gemini URL 系列模型，需要添加 responseModalities 配置
    # 只要求输出图片，不输出文本
    if is_gemini_url_model:
        generation_config["responseModalities"] = ["IMAGE"]
    
    # Add seed if provided
    # 注释掉：不再传递种子参数到 API
    # if seed is not None:
    #     generation_config["seed"] = seed
    
    # Complete request body
    # 对于 Gemini URL 系列模型，需要添加 role 字段
    if is_gemini_url_model:
        body = {
            "contents": [{
                "role": "user",
                "parts": parts
            }],
            "generationConfig": generation_config
        }
    else:
        body = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": generation_config
        }
    
    logger.debug(f"Request body structure: {list(body.keys())}")
    logger.debug(f"imageConfig: {image_config}")
    
    # 单次请求，不自动重试（避免 504 等超时错误导致重复扣费）
    try:
        # 调试日志
        mode = "图生图" if reference_images_base64 else "文生图"
        num_refs = len(reference_images_base64) if reference_images_base64 else 0
        logger.debug(f"正在生成图片... ({mode}, 参考图{num_refs}张)")
        logger.debug(f"Model: {model}, Aspect: {aspect_ratio}, Size: {image_size}, Seed: {seed}")
        logger.debug(f"Prompt: {prompt[:100]}...")
        
        # 构建代理配置：优先使用用户传入的 proxy，其次使用全局配置
        user_proxy = proxy.strip() if proxy else None
        active_proxy = user_proxy or PROXY_URL
        proxies_dict = {"http": active_proxy, "https": active_proxy} if active_proxy else None
        
        # 简化日志输出
        print(f"\n⏱️ 发送请求...", flush=True)
        if active_proxy:
            print(f"    🔀 代理: 已启用", flush=True)
        else:
            print(f"    🔀 代理: 未启用（直连）", flush=True)
        
        _t_request = time.time()
        
        # 统一采用一次性读取，不使用流式读取
        is_b64_response = is_gemini_b64_model
        use_stream = False  # 统一禁用流式读取，采用一次性读取
        
        # 根据是否使用代理调整超时时间
        # 使用代理时，连接超时需要更长（SSL握手通过代理需要更多时间）
        if active_proxy:
            # 使用代理：连接超时120秒，读取超时600秒
            connect_timeout = 120
            read_timeout = 600
        else:
            # 直连：连接超时60秒，读取超时600秒
            connect_timeout = 60
            read_timeout = 600
        
        response = requests.post(
            base_url,
            headers=headers,
            json=body,
            timeout=(connect_timeout, read_timeout),
            verify=False,
            stream=use_stream,  # 统一禁用流式读取
            proxies=proxies_dict
        )
        _t_connect = time.time() - _t_request
        
        # 确认代理使用情况并显示连接建立
        if active_proxy:
            via_header = response.headers.get('Via', '')
            if via_header:
                print(f"    ✅ 代理已生效, 连接建立: {_t_connect:.2f}s", flush=True)
            else:
                print(f"    ✅ 代理已应用, 连接建立: {_t_connect:.2f}s", flush=True)
        else:
            print(f"    ✅ 连接建立: {_t_connect:.2f}s", flush=True)
        
        # Check if request was successful
        if response.status_code == 200:
            try:
                _t_download = time.time()
                
                # 统一采用一次性读取
                content = response.content  # 一次性读取全部内容
                _download_time = time.time() - _t_download
                
                _t_json = time.time()
                response_json = json.loads(content.decode('utf-8'))
                _t_json_parse = time.time() - _t_json
                
                # 只显示总耗时
                total_time = _t_connect + _download_time + _t_json_parse
                print(f"    ⏱️  总耗时: {total_time:.3f}s", flush=True)
                
                return response_json
            except json.JSONDecodeError as e:
                logger.warning(f"响应不是有效的 JSON 格式: {str(e)}")
                raise Exception("API 返回了非 JSON 格式的响应")
        else:
            # 解析错误响应，检测特定错误类型
            error_text = response.text
            friendly_error = parse_api_error(response.status_code, error_text)
            logger.error(f"请求错误: {response.status_code}")
            
            # 检测模型未配置的错误
            if "model_not_found" in error_text or "无可用渠道" in error_text:
                friendly_msg = (
                    f"❌ 模型暂时不可用\n\n"
                    f"当前所选模型暂时无法使用，可能正在维护中。\n\n"
                    f"💡 解决方法：\n"
                    f"   • 请稍后重试\n"
                    f"   • 或联系技术支持获取帮助"
                )
                raise Exception(friendly_msg)
            
            # 客户端错误 (4xx)
            if response.status_code == 401:
                raise Exception("❌ API密钥无效或已过期，请检查您的密钥配置")
            elif response.status_code == 429:
                raise Exception("❌ 请求过于频繁，请稍后再试")
            elif response.status_code == 504:
                raise Exception(
                    f"❌ 服务器响应超时\n\n"
                    f"💡 提示：\n"
                    f"   • 生成高清图片需要较长时间\n"
                    f"   • 请求可能已在处理中\n"
                    f"   • 建议先用 2K 测试，再生成 4K\n"
                    f"   • 如需重试，请手动重新运行"
                )
            else:
                raise Exception(f"❌ 服务器错误，建议稍后重试或降低图片清晰度")
                
    except requests.exceptions.Timeout:
        print(f"⏰ 请求超时 (超过10分钟)")
        raise Exception(
            "❌ 请求超时\n\n"
            "💡 提示：\n"
            "   • 生成高清图片需要较长时间\n"
            "   • 请求可能已在服务端处理中\n"
            "   • 建议稍后检查是否已扣费，避免重复提交"
        )
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络连接失败")
        logger.error(f"Network error: {str(e)}")
        raise Exception(f"❌ 网络连接失败\n💡 请检查网络连接后重试")


def extract_image_from_gemini_response(response_data, proxy=""):
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
       注意：base64 格式的图片数据已在 JSON 响应中，无需额外下载，只需本地解码即可。
       适用于：gemini-3-pro-image-preview 系列模型
    
    2. URL format with URL in text:
       {
         "candidates": [{
           "content": {
             "parts": [{
               "text": "![image](https://...)"
             }]
           }
         }]
       }
       注意：URL 格式需要从响应中提取 URL，然后额外发起 HTTP 请求下载图片文件
    
    Args:
        response_data (dict): Gemini API response
        proxy (str): 可选的代理地址，用于下载图片（仅 URL 格式需要）
        
    Returns:
        PIL.Image: Extracted image
    """
    try:
        _t_extract = time.time()
        print(f"\n⏱️ 正在提取图片数据...", flush=True)
        
        # Navigate the response structure
        if 'candidates' not in response_data or len(response_data['candidates']) == 0:
            logger.error(f"响应结构异常: 缺少 candidates")
            raise Exception("服务器响应格式异常")
        
        candidate = response_data['candidates'][0]
        
        # 检查是否有错误的 finishReason
        finish_reason = candidate.get('finishReason', '')
        
        # 调试：打印 finishReason
        if finish_reason and finish_reason != 'STOP':
            logger.warning(f"finishReason: {finish_reason}")
        
        # 处理 MALFORMED_FUNCTION_CALL 错误
        if finish_reason == 'MALFORMED_FUNCTION_CALL':
            finish_message = candidate.get('finishMessage', '')
            logger.error(f"模型调用异常: {finish_reason}")
            if finish_message:
                logger.error(f"错误详情: {finish_message[:200]}")
            raise Exception(
                "❌ 服务器处理异常\n\n"
                "💡 建议：\n"
                "   • 这是服务端的临时错误，请稍后重试\n"
                "   • 如持续出现，可尝试简化提示词"
            )
        
        # 处理其他非正常结束原因
        if finish_reason and finish_reason not in ['STOP', 'MAX_TOKENS', '']:
            logger.warning(f"响应异常终止: {finish_reason}")
            # 根据不同原因给出提示
            reason_messages = {
                'SAFETY': "内容被安全过滤器拦截，请修改提示词",
                'RECITATION': "内容因版权问题被拦截",
                'OTHER': "服务器返回未知错误，请稍后重试",
            }
            msg = reason_messages.get(finish_reason, f"服务器异常终止: {finish_reason}")
            raise Exception(msg)
        
        if 'content' not in candidate or 'parts' not in candidate['content']:
            # 检查 content 是否为空对象
            content = candidate.get('content', {})
            is_empty_content = (content == {} or content is None)
            
            logger.error(f"响应结构异常: 缺少 content 或 parts")
            
            if is_empty_content:
                raise Exception(
                    "❌ 服务器返回了空的响应\n\n"
                    "💡 建议：\n"
                    "   • 这通常是服务端的临时问题\n"
                    "   • 请稍后重试"
                )
            raise Exception("服务器响应格式异常")
        
        parts = candidate['content']['parts']
        
        # Try to find inline_data (official Gemini format) first
        for part_idx, part in enumerate(parts):
            if 'inline_data' in part or 'inlineData' in part:
                inline_data = part.get('inline_data') or part.get('inlineData')
                
                # 处理两种格式：
                # 1. 标准格式: {"mime_type": "...", "data": "base64..."}
                # 2. SVIP格式: 直接是 base64 字符串
                if isinstance(inline_data, dict):
                    # 标准 Gemini 格式
                    base64_data = inline_data.get('data')
                    if base64_data:
                        _t_decode = time.time()
                        result = decode_base64_image(base64_data)
                        _t_decode_time = time.time() - _t_decode
                        print(f"    ✅ 提取完成: 耗时 {_t_decode_time:.2f}s", flush=True)
                        return result
                elif isinstance(inline_data, str):
                    # SVIP 格式：直接是 base64 字符串
                    _t_decode = time.time()
                    result = decode_base64_image(inline_data)
                    _t_decode_time = time.time() - _t_decode
                    print(f"    ✅ 提取完成: 耗时 {_t_decode_time:.2f}s", flush=True)
                    return result
        
        # If no inline_data, try to extract URL from text
        # 注意：URL 格式需要额外下载图片文件，而 base64 格式已在响应中，只需本地解码
        for part_idx, part in enumerate(parts):
            if 'text' in part:
                text = part['text']
                logger.debug(f"Checking text field for image URL...")
                
                # Extract URL from markdown format: ![image](URL)
                import re
                markdown_match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', text)
                if markdown_match:
                    url = markdown_match.group(1)
                    # 显示代理信息（如果使用代理）
                    user_proxy = proxy.strip() if proxy else None
                    active_proxy = user_proxy or PROXY_URL
                    if active_proxy:
                        print(f"    🔀 代理: 已启用", flush=True)
                    result = download_image_from_url(url, proxy=proxy)
                    print(f"    ✅ 提取完成: 耗时 {time.time()-_t_extract:.2f}s", flush=True)
                    return result
                
                # Try to find plain HTTP URL
                url_match = re.search(r'(https?://[^\s\)]+\.(?:png|jpg|jpeg|webp|gif))', text, re.IGNORECASE)
                if url_match:
                    url = url_match.group(1)
                    # 显示代理信息（如果使用代理）
                    user_proxy = proxy.strip() if proxy else None
                    active_proxy = user_proxy or PROXY_URL
                    if active_proxy:
                        print(f"    🔀 代理: 已启用", flush=True)
                    result = download_image_from_url(url, proxy=proxy)
                    print(f"    ✅ 提取完成: 耗时 {time.time()-_t_extract:.2f}s", flush=True)
                    return result
        
        # If we get here, no image data was found
        logger.error(f"响应中未找到图片数据，Parts 数量: {len(parts)}")
        raise Exception(
            "❌ 响应中未找到图片数据\n\n"
            "💡 建议：\n"
            "   • 这可能是提示词触发了异常\n"
            "   • 请尝试使用英文提示词或简化提示词\n"
            "   • 如持续出现，请稍后重试"
        )
        
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
        return image
    except Exception as e:
        logger.error(f"Failed to decode base64 image: {str(e)}")
        raise


def download_image_from_url(url, max_retries=3, proxy=""):
    """
    Download image from URL and convert to PIL Image
    
    Args:
        url (str): URL of the image
        max_retries (int): Maximum number of retry attempts
        proxy (str): 可选的代理地址
        
    Returns:
        PIL.Image: Downloaded image
    """
    logger.debug(f"正在下载图片")
    
    # 构建代理配置：优先使用用户传入的 proxy，其次使用全局配置
    user_proxy = proxy.strip() if proxy else None
    active_proxy = user_proxy or PROXY_URL
    proxies_dict = {"http": active_proxy, "https": active_proxy} if active_proxy else None
    
    # 注意：代理信息已在 extract_image_from_gemini_response 中显示，这里不再重复显示
    
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"   重试下载 ({attempt}/{max_retries})...", flush=True)
                time.sleep(2)  # 重试前等待2秒
            
            # 使用 stream=True 分块下载，更好地处理大文件和超时
            response = requests.get(
                url, 
                timeout=(10, 120),  # (连接超时, 读取超时) - 连接10秒，读取120秒
                verify=False,  # 禁用 SSL 验证
                stream=True,
                proxies=proxies_dict  # 使用代理加速下载
            )
            response.raise_for_status()
            
            # 确认代理使用情况（仅在提取图片数据阶段显示）
            if active_proxy:
                via_header = response.headers.get('Via', '')
                if via_header:
                    print(f"    ✅ 代理已生效", flush=True)
                else:
                    print(f"    ✅ 代理已应用", flush=True)
            
            # 获取内容长度（如果有）
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                logger.debug(f"Image size: {size_mb:.2f} MB")
            
            # 读取全部内容
            image_data = response.content
            image = Image.open(io.BytesIO(image_data))
            return image
            
        except requests.exceptions.ConnectTimeout:
            last_error = "连接超时，无法连接到图片服务器"
            logger.warning(f"Connection timeout (attempt {attempt}/{max_retries})")
        except requests.exceptions.ReadTimeout:
            last_error = "读取超时，下载图片时间过长"
            logger.warning(f"Read timeout (attempt {attempt}/{max_retries})")
        except requests.exceptions.ConnectionError as e:
            last_error = f"网络连接错误: {str(e)}"
            logger.warning(f"Connection error (attempt {attempt}/{max_retries}): {str(e)}")
        except requests.exceptions.HTTPError as e:
            # HTTP 错误（4xx, 5xx）不重试
            status_code = e.response.status_code if e.response else "unknown"
            logger.error(f"HTTP error {status_code}: {str(e)}")
            raise Exception(f"下载图片失败: 图片链接可能已过期或不可访问")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Download error (attempt {attempt}/{max_retries}): {str(e)}")
    
    # 所有重试都失败了
    error_msg = (
        f"❌ 图片下载失败\n\n"
        f"💡 提示：\n"
        f"   • 图片已在服务端生成成功\n"
        f"   • 但下载图片时遇到网络问题\n"
        f"   • 错误: {last_error}\n"
        f"   • 建议检查网络连接后重试"
    )
    logger.error(f"Failed to download image after {max_retries} attempts: {last_error}")
    raise Exception(error_msg)


# ============================================================
# 图像缩放相关配置
# ============================================================

# 支持的缩放方法（PIL Resampling）
UPSCALE_METHODS = {
    "lanczos": Image.Resampling.LANCZOS,
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "box": Image.Resampling.BOX,
    "hamming": Image.Resampling.HAMMING,
}

# 支持的最大尺寸选项
MAX_DIM_OPTIONS = ["auto", "512", "768", "1024", "1280", "1536", "2048", "2560", "3072", "4096"]


def resize_image_to_max_dim(pil_image, max_dim="auto", upscale_method="lanczos"):
    """
    将图像缩放到指定的最大尺寸（保持宽高比）
    
    Args:
        pil_image (PIL.Image): PIL 图像对象
        max_dim (str): 最大尺寸，"auto" 表示不缩放，或数字字符串如 "512", "1024"
        upscale_method (str): 缩放方法，如 "lanczos", "bilinear" 等
        
    Returns:
        PIL.Image: 缩放后的图像（如果 max_dim 为 "auto" 则返回原图）
    """
    # 如果是 auto 或空值，不做任何处理
    if max_dim == "auto" or not max_dim:
        return pil_image
    
    try:
        target_max_dim = int(max_dim)
    except ValueError:
        logger.warning(f"无效的 max_dim 值: {max_dim}，跳过缩放")
        return pil_image
    
    # 获取当前尺寸
    width, height = pil_image.size
    current_max_dim = max(width, height)
    
    # 如果图像已经小于等于目标尺寸，不做处理
    if current_max_dim <= target_max_dim:
        logger.debug(f"图像尺寸 {width}x{height} 已满足要求，无需缩放")
        return pil_image
    
    # 计算缩放比例
    scale = target_max_dim / current_max_dim
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    # 获取缩放方法
    resample_method = UPSCALE_METHODS.get(upscale_method.lower(), Image.Resampling.LANCZOS)
    
    # 执行缩放
    logger.debug(f"缩放图像: {width}x{height} -> {new_width}x{new_height} (方法: {upscale_method})")
    resized_image = pil_image.resize((new_width, new_height), resample=resample_method)
    
    return resized_image


def resize_comfy_image_to_max_dim(image_tensor, max_dim="auto", upscale_method="lanczos"):
    """
    将 ComfyUI 图像张量缩放到指定的最大尺寸（保持宽高比）
    
    Args:
        image_tensor (torch.Tensor): ComfyUI 图像张量 (B, H, W, C)
        max_dim (str): 最大尺寸，"auto" 表示不缩放
        upscale_method (str): 缩放方法
        
    Returns:
        torch.Tensor: 缩放后的图像张量
    """
    # 如果是 auto，直接返回原图
    if max_dim == "auto" or not max_dim:
        return image_tensor
    
    # 处理批量图像
    batch_size = image_tensor.shape[0]
    resized_images = []
    
    for i in range(batch_size):
        # 提取单张图像并转换为 PIL
        single_image = image_tensor[i]  # (H, W, C)
        np_image = (single_image.numpy() * 255).astype(np.uint8)
        pil_image = Image.fromarray(np_image)
        
        # 缩放
        resized_pil = resize_image_to_max_dim(pil_image, max_dim, upscale_method)
        
        # 转回张量
        resized_np = np.array(resized_pil).astype(np.float32) / 255.0
        resized_tensor = torch.from_numpy(resized_np)
        resized_images.append(resized_tensor)
    
    # 合并为批量张量
    # 注意：如果图像尺寸不同，需要特殊处理
    # 但由于都按同一比例缩放，尺寸应该相同
    result = torch.stack(resized_images, dim=0)
    
    return result


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


def process_api_response(response_data, proxy=""):
    """
    Process API response and return PIL Image
    
    支持两种格式:
    1. Gemini 格式 - 从 candidates/content/parts 中提取图片
    2. OpenAI 格式 - 直接从包装的 _openai_pil_image 字段获取
    
    Args:
        response_data (dict): API response data
        proxy (str): 可选的代理地址，用于下载图片
        
    Returns:
        PIL.Image: Generated image
    """
    try:
        # 检查是否是 OpenAI 格式的包装响应
        if "_openai_pil_image" in response_data:
            return response_data["_openai_pil_image"]
        
        # 原有逻辑：处理 Gemini 格式
        return extract_image_from_gemini_response(response_data, proxy=proxy)
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
