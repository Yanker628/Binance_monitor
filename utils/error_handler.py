"""错误处理和安全模块"""
import logging
import traceback
from typing import Any, Dict, Optional, Callable
from enum import Enum
import requests
import ssl
import json

logger = logging.getLogger('binance_monitor')


class ErrorType(Enum):
    NETWORK_ERROR = "network_error"
    SSL_ERROR = "ssl_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    DATA_VALIDATION_ERROR = "data_validation_error"
    CONFIGURATION_ERROR = "configuration_error"
    API_ERROR = "api_error"
    WEBSOCKET_ERROR = "websocket_error"
    TELEGRAM_ERROR = "telegram_error"
    UNKNOWN_ERROR = "unknown_error"


class SecurityError(Exception):
    def __init__(self, message: str, error_type: ErrorType = ErrorType.UNKNOWN_ERROR):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.error_counts: Dict[ErrorType, int] = {}
        self.max_error_count = 10
        self.error_callbacks: Dict[ErrorType, Callable] = {}
    
    def register_error_callback(self, error_type: ErrorType, callback: Callable):
        self.error_callbacks[error_type] = callback
    
    def handle_error(self, error: Exception, context: str = "", 
                    error_type: Optional[ErrorType] = None) -> bool:
        try:
            if error_type is None:
                error_type = self._classify_error(error)
            
            self._log_error(error, error_type, context)
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
            
            if self.error_counts[error_type] > self.max_error_count:
                logger.critical(f"❌ {error_type.value} 错误次数过多，可能需要人工干预")
                return False
            
            if error_type in self.error_callbacks:
                try:
                    self.error_callbacks[error_type](error, context)
                except Exception as callback_error:
                    logger.error(f"❌ 错误回调执行失败: {callback_error}")
            
            return self._should_continue(error_type)
            
        except Exception as e:
            logger.error(f"❌ 错误处理器本身出错: {e}")
            return False
    
    def _classify_error(self, error: Exception) -> ErrorType:
        if isinstance(error, requests.exceptions.RequestException):
            if isinstance(error, requests.exceptions.SSLError):
                return ErrorType.SSL_ERROR
            elif isinstance(error, requests.exceptions.ConnectionError):
                return ErrorType.NETWORK_ERROR
            elif isinstance(error, requests.exceptions.Timeout):
                return ErrorType.NETWORK_ERROR
            elif hasattr(error, 'response') and error.response:
                status_code = error.response.status_code
                if status_code == 401:
                    return ErrorType.AUTHENTICATION_ERROR
                elif status_code == 429:
                    return ErrorType.RATE_LIMIT_ERROR
                elif 400 <= status_code < 500:
                    return ErrorType.API_ERROR
                elif 500 <= status_code < 600:
                    return ErrorType.API_ERROR
            return ErrorType.NETWORK_ERROR
        
        elif isinstance(error, ssl.SSLError):
            return ErrorType.SSL_ERROR
        
        elif isinstance(error, SecurityError):
            return error.error_type
        
        elif isinstance(error, ValueError):
            return ErrorType.DATA_VALIDATION_ERROR
        
        elif isinstance(error, ConnectionError):
            return ErrorType.WEBSOCKET_ERROR
        
        elif isinstance(error, json.JSONDecodeError):
            return ErrorType.DATA_VALIDATION_ERROR
        
        else:
            return ErrorType.UNKNOWN_ERROR
    
    def _log_error(self, error: Exception, error_type: ErrorType, context: str):
        error_msg = f"[{error_type.value}] {context}: {str(error)}"
        
        if error_type in [ErrorType.AUTHENTICATION_ERROR, ErrorType.SSL_ERROR]:
            logger.critical(error_msg)
        elif error_type in [ErrorType.NETWORK_ERROR, ErrorType.API_ERROR]:
            logger.error(error_msg)
        elif error_type in [ErrorType.RATE_LIMIT_ERROR, ErrorType.WEBSOCKET_ERROR]:
            logger.warning(error_msg)
        else:
            logger.error(error_msg)
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"错误堆栈:\n{traceback.format_exc()}")
    
    def _should_continue(self, error_type: ErrorType) -> bool:
        if error_type in [ErrorType.AUTHENTICATION_ERROR, ErrorType.SSL_ERROR]:
            return False
        
        if error_type == ErrorType.CONFIGURATION_ERROR:
            return False
        
        return True
    
    def reset_error_count(self, error_type: Optional[ErrorType] = None):
        if error_type:
            self.error_counts[error_type] = 0
        else:
            self.error_counts.clear()
    
    def get_error_count(self, error_type: ErrorType) -> int:
        return self.error_counts.get(error_type, 0)


class SafeRequestHandler:
    """安全请求处理器"""
    
    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
    
    def safe_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            headers = kwargs.get('headers', {})
            headers.update({
                'User-Agent': 'BinanceMonitor/1.0',
                'Accept': 'application/json',
                'Connection': 'close'
            })
            kwargs['headers'] = headers
            
            if 'timeout' not in kwargs:
                kwargs['timeout'] = (5, 30)
            
            kwargs['verify'] = True
            
            logger.debug(f"🔒 发送安全请求: {method} {url}")
            
            response = requests.request(method, url, **kwargs)
            
            if response.status_code >= 400:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                raise requests.exceptions.HTTPError(error_msg)
            
            logger.debug(f"✅ 请求成功: {method} {url} - {response.status_code}")
            return response
            
        except Exception as e:
            self.error_handler.handle_error(e, f"HTTP请求失败: {method} {url}")
            return None


class SafeWebSocketHandler:
    """安全WebSocket处理器"""
    
    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
    
    def safe_websocket_connect(self, ws_url: str, **kwargs) -> bool:
        try:
            if not ws_url.startswith(('wss://', 'ws://')):
                raise SecurityError(f"无效的WebSocket URL: {ws_url}", ErrorType.WEBSOCKET_ERROR)
            
            if ws_url.startswith('ws://') and 'testnet' not in ws_url:
                logger.warning(f"⚠️ 生产环境建议使用WSS: {ws_url}")
            
            logger.debug(f"🔒 建立安全WebSocket连接: {ws_url}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, f"WebSocket连接失败: {ws_url}")
            return False


class SafeDataHandler:
    """安全数据处理器"""
    
    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
    
    def safe_json_parse(self, data: str, context: str = "") -> Optional[Dict[str, Any]]:
        try:
            if not data or not isinstance(data, str):
                raise ValueError("无效的JSON数据")
            
            if len(data) > 1024 * 1024:
                raise ValueError("JSON数据过大")
            
            parsed = json.loads(data)
            
            if not isinstance(parsed, dict):
                raise ValueError("JSON数据不是字典格式")
            
            logger.debug(f"✅ JSON解析成功: {context}")
            return parsed
            
        except Exception as e:
            self.error_handler.handle_error(e, f"JSON解析失败: {context}")
            return None
    
    def safe_data_extraction(self, data: Dict[str, Any], 
                           required_fields: list, 
                           context: str = "") -> Optional[Dict[str, Any]]:
        try:
            if not isinstance(data, dict):
                raise ValueError("数据不是字典格式")
            
            extracted = {}
            for field in required_fields:
                if field not in data:
                    logger.warning(f"⚠️ 缺少必需字段: {field} in {context}")
                    return None
                
                extracted[field] = data[field]
            
            logger.debug(f"✅ 数据提取成功: {context}")
            return extracted
            
        except Exception as e:
            self.error_handler.handle_error(e, f"数据提取失败: {context}")
            return None


global_error_handler = ErrorHandler()

def default_network_error_callback(error: Exception, context: str):
    logger.warning(f"🌐 网络错误，将尝试重连: {context}")

def default_auth_error_callback(error: Exception, context: str):
    logger.critical(f"🔐 认证失败，请检查API密钥: {context}")

def default_rate_limit_callback(error: Exception, context: str):
    logger.warning(f"⏰ API限流，将等待后重试: {context}")

global_error_handler.register_error_callback(ErrorType.NETWORK_ERROR, default_network_error_callback)
global_error_handler.register_error_callback(ErrorType.AUTHENTICATION_ERROR, default_auth_error_callback)
global_error_handler.register_error_callback(ErrorType.RATE_LIMIT_ERROR, default_rate_limit_callback)
