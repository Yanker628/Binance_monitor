"""币安REST API客户端"""
import time
import logging
import requests
from typing import Dict, List, Any, Optional
from .auth import BinanceAuth

logger = logging.getLogger('binance_monitor')


class BinanceClient:
    """币安合约REST API客户端"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str, max_retries: int = 3):
        self.auth = BinanceAuth(api_key, api_secret)
        self.base_url = base_url
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({'X-MBX-APIKEY': api_key})
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = False) -> Any:
        """
        发送HTTP请求，带重试机制
        
        Args:
            method: HTTP方法
            endpoint: API端点
            params: 请求参数
            signed: 是否需要签名
            
        Returns:
            API响应的JSON数据
            
        Raises:
            requests.exceptions.RequestException: 请求失败
        """
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        
        if signed:
            params = self.auth.sign_request(params)
        
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(method, url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"API请求超时 (尝试 {attempt}/{self.max_retries}): {method} {endpoint}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)  # 指数退避：2, 4, 8秒
                    
            except requests.exceptions.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if e.response else 0
                
                # 429 Too Many Requests - 需要重试
                # 5xx Server Error - 需要重试
                if status_code == 429 or (500 <= status_code < 600):
                    logger.warning(f"API请求错误 {status_code} (尝试 {attempt}/{self.max_retries}): {method} {endpoint}")
                    if attempt < self.max_retries:
                        retry_after = int(e.response.headers.get('Retry-After', 2 ** attempt))
                        time.sleep(min(retry_after, 30))  # 最多等待30秒
                else:
                    # 4xx Client Error (除了429) - 不重试，直接抛出
                    error_text = ''
                    try:
                        error_text = e.response.text
                    except Exception:
                        error_text = '<无法读取响应内容>'
                    raise requests.exceptions.RequestException(
                        f"HTTP {method} {endpoint} 失败 (状态码 {status_code}): {error_text}"
                    ) from e
                    
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"API请求异常 (尝试 {attempt}/{self.max_retries}): {method} {endpoint} - {str(e)}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        
        # 所有重试都失败了
        error_msg = f"API请求失败，已重试 {self.max_retries} 次: {method} {endpoint}"
        if last_exception:
            raise requests.exceptions.RequestException(error_msg) from last_exception
        else:
            raise requests.exceptions.RequestException(error_msg)
    
    def start_user_data_stream(self, endpoint: str = '/v1/listenKey') -> str:
        response = self._request('POST', endpoint)
        return response.get('listenKey', '')
    
    def keepalive_user_data_stream(self, listen_key: str, endpoint: str = '/v1/listenKey') -> Dict:
        return self._request('PUT', endpoint, {'listenKey': listen_key})
    
    def close_user_data_stream(self, listen_key: str, endpoint: str = '/v1/listenKey') -> Dict:
        return self._request('DELETE', endpoint, {'listenKey': listen_key})

