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
        # 网络线路映射（内部使用，不对外暴露）
        # 通过编码方式隐藏实际地址
        _net_map = {
            "A-全球加速线路": "aHR0cHM6Ly9hcGkuYWFiYW8udG9w",  # base64 encoded
            "A-国内加速线路": "aHR0cHM6Ly9oay1hcGkuYWFiYW8udG9w",  # base64 encoded
        }
        
        # 解码网络线路URL
        if network and network in _net_map:
            import base64
            network_url = base64.b64decode(_net_map[network]).decode('utf-8')
        else:
            network_url = None
            network = "不加速"
        
        logger.debug(f"配置加载完成")
        
        # 返回配置元组
        return ((api_key, network_url, proxy, network),)
