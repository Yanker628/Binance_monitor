"""币安API认证模块"""
import time
import hmac
import hashlib
from typing import Dict, Any
from urllib.parse import urlencode


class BinanceAuth:
    """币安API认证工具类"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def generate_signature(self, params: Dict[str, Any]) -> str:
        """
        生成HMAC SHA256签名
        
        Args:
            params: 请求参数字典
            
        Returns:
            签名字符串
        """
        # 按字母顺序排序参数
        sorted_params = sorted(params.items())
        query_string = urlencode(sorted_params)
        
        # 生成签名
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def sign_request(self, params: Dict[str, Any], recv_window: int = 5000) -> Dict[str, Any]:
        """
        为请求添加签名和时间戳
        
        Args:
            params: 原始请求参数
            recv_window: 接收窗口时间（毫秒）
            
        Returns:
            包含签名的完整参数字典
        """
        # 添加时间戳
        params['timestamp'] = int(time.time() * 1000)
        
        # 添加接收窗口
        if recv_window:
            params['recvWindow'] = recv_window
        
        # 生成并添加签名（注意：签名payload中不包含apiKey）
        params['signature'] = self.generate_signature(params)
        
        return params
