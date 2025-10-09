"""币安REST API客户端"""
import time
import logging
import requests
from typing import Dict, List, Any, Optional
from .auth import BinanceAuth
from utils.error_handler import global_error_handler, SafeRequestHandler, ErrorType
from utils.common import RetryManager, global_rate_limiter

logger = logging.getLogger('binance_monitor')


class BinanceClient:
    """币安合约REST API客户端"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str, max_retries: int = 3):
        self.auth = BinanceAuth(api_key, api_secret)
        self.base_url = base_url
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({'X-MBX-APIKEY': api_key})
        
        self.safe_handler = SafeRequestHandler(global_error_handler)
        self._configure_secure_session()
        
        logger.info(f"🔒 币安客户端已初始化，安全模式已启用")
    
    def _configure_secure_session(self):
        try:
            self.session.headers.update({
                'User-Agent': 'BinanceMonitor/1.0',
                'Accept': 'application/json',
                'Connection': 'close'
            })
            
            self.session.verify = True
            
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            
            logger.info("✅ 安全会话配置完成")
            
        except Exception as e:
            logger.error(f"❌ 安全会话配置失败: {e}")
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = False) -> Any:
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        
        if signed:
            params = self.auth.sign_request(params)
        
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"🔒 发送安全请求: {method} {endpoint} (尝试 {attempt}/{self.max_retries})")
                
                response = self.session.request(
                    method, url, 
                    params=params, 
                    timeout=(5, 30),
                    verify=True
                )
                
                if response.status_code >= 400:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    
                    if response.status_code == 401:
                        error_type = ErrorType.AUTHENTICATION_ERROR
                    elif response.status_code == 429:
                        error_type = ErrorType.RATE_LIMIT_ERROR
                    elif 400 <= response.status_code < 500:
                        error_type = ErrorType.API_ERROR
                    elif 500 <= response.status_code < 600:
                        error_type = ErrorType.API_ERROR
                    else:
                        error_type = ErrorType.API_ERROR
                    
                    if not global_error_handler.handle_error(
                        requests.exceptions.HTTPError(error_msg), 
                        f"{method} {endpoint}", 
                        error_type
                    ):
                        raise requests.exceptions.RequestException(error_msg)
                
                response.raise_for_status()
                
                try:
                    result = response.json()
                    logger.debug(f"✅ 请求成功: {method} {endpoint}")
                    return result
                except ValueError as e:
                    logger.error(f"❌ JSON解析失败: {e}")
                    raise requests.exceptions.RequestException(f"响应不是有效的JSON: {e}")
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"⏰ API请求超时 (尝试 {attempt}/{self.max_retries}): {method} {endpoint}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.SSLError as e:
                last_exception = e
                logger.error(f"🔒 SSL错误 (尝试 {attempt}/{self.max_retries}): {method} {endpoint}")
                if not global_error_handler.handle_error(e, f"{method} {endpoint}", ErrorType.SSL_ERROR):
                    raise e
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.warning(f"🌐 连接错误 (尝试 {attempt}/{self.max_retries}): {method} {endpoint}")
                if not global_error_handler.handle_error(e, f"{method} {endpoint}", ErrorType.NETWORK_ERROR):
                    raise e
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if e.response else 0
                
                if status_code == 429 or (500 <= status_code < 600):
                    logger.warning(f"⚠️ API请求错误 {status_code} (尝试 {attempt}/{self.max_retries}): {method} {endpoint}")
                    if attempt < self.max_retries:
                        retry_after = int(e.response.headers.get('Retry-After', 2 ** attempt))
                        time.sleep(min(retry_after, 30))
                else:
                    error_text = ''
                    try:
                        error_text = e.response.text
                    except Exception:
                        error_text = '<无法读取响应内容>'
                    
                    error_msg = f"HTTP {method} {endpoint} 失败 (状态码 {status_code}): {error_text}"
                    
                    error_type = ErrorType.AUTHENTICATION_ERROR if status_code == 401 else ErrorType.API_ERROR
                    if not global_error_handler.handle_error(e, error_msg, error_type):
                        raise requests.exceptions.RequestException(error_msg) from e
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"❌ API请求异常 (尝试 {attempt}/{self.max_retries}): {method} {endpoint} - {str(e)}")
                if not global_error_handler.handle_error(e, f"{method} {endpoint}"):
                    raise e
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        
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
        url = f"{self.base_url}{endpoint}"
        params = {'listenKey': listen_key}
        params = self.auth.sign_request(params)
        
        try:
            response = self.session.request(
                'DELETE', url,
                params=params,
                timeout=(5, 30),
                verify=True
            )
            
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    if error_data.get('code') == -1125:
                        logger.debug(f"🔑 listenKey已过期或不存在，跳过删除: {listen_key[:20]}...")
                        return {'msg': 'listenKey already expired'}
                except (ValueError, KeyError):
                    pass
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    if error_data.get('code') == -1125:
                        logger.debug(f"🔑 listenKey已过期或不存在，跳过删除: {listen_key[:20]}...")
                        return {'msg': 'listenKey already expired'}
                except (ValueError, KeyError):
                    pass
            raise

