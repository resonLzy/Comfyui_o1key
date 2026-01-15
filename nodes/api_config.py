"""
ComfyUI node for API configuration
用于统一管理API相关配置，支持连接到其他节点
"""
import logging

logger = logging.getLogger(__name__)


class NanoBananaAPIConfig:
    """
    API配置节点：统一管理API密钥、网络线路和代理设置
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "placeholder": "输入您的API密钥"
                }),
                "proxy": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "placeholder": "http://127.0.0.1:7890 (可选)"
                }),
            },
            "optional": {
                "network": ([
                    "不加速",
                    "A-全球加速线路",
                    "A-国内加速线路",
                ], {
                    "default": "不加速"
                }),
            }
        }
    
    RETURN_TYPES = ("APICONFIG",)
    RETURN_NAMES = ("api_config",)
    FUNCTION = "get_config"
    CATEGORY = "o1key/config"
    
    def get_config(self, api_key, proxy="", network="不加速"):
        """
        返回配置信息
        
        Returns:
            tuple: (api_key, network_url, proxy, network_name) 作为配置对象
        """
        # 网络线路映射（如果network为"不加速"或空，则不使用加速节点）
        network_urls = {
            "A-全球加速线路": "https://api.aabao.top",
            "A-国内加速线路": "https://hk-api.aabao.top",
        }
        
        # 如果network为"不加速"或不在映射中，network_url为None
        if network and network in network_urls:
            network_url = network_urls[network]
        else:
            network_url = None
            network = "不加速"  # 确保network为"不加速"
        
        logger.debug(f"API配置 - 网络: {network}, 代理: {proxy or '未使用'}")
        
        # 返回配置元组，作为配置对象（包含network名称用于显示）
        return ((api_key, network_url, proxy, network),)
