"""通用工具模块"""
import time
import logging
from typing import Any, Dict, List, Optional, Callable, Union
from functools import wraps
from datetime import datetime

logger = logging.getLogger('binance_monitor')


class RetryManager:
    """重试管理器"""
    
    @staticmethod
    def retry_on_exception(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
        """重试装饰器"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                current_delay = delay
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries:
                            logger.warning(f"重试 {attempt + 1}/{max_retries}: {func.__name__} - {str(e)}")
                            time.sleep(current_delay)
                            current_delay *= backoff
                        else:
                            logger.error(f"重试失败，已尝试 {max_retries} 次: {func.__name__}")
                
                if last_exception:
                    raise last_exception
                else:
                    raise RuntimeError(f"重试失败，已尝试 {max_retries} 次: {func.__name__}")
            return wrapper
        return decorator


class RateLimiter:
    """频率限制器"""
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: List[float] = []
    
    def is_allowed(self) -> bool:
        """检查是否允许请求"""
        now = time.time()
        self.requests = [req_time for req_time in self.requests if now - req_time < self.window_seconds]
        
        if len(self.requests) >= self.max_requests:
            logger.warning(f"频率限制: {len(self.requests)}/{self.max_requests} 请求在 {self.window_seconds} 秒内")
            return False
        
        self.requests.append(now)
        return True
    
    def wait_if_needed(self):
        """如果需要则等待"""
        if not self.is_allowed():
            oldest_request = min(self.requests)
            wait_time = self.window_seconds - (time.time() - oldest_request)
            if wait_time > 0:
                logger.info(f"频率限制，等待 {wait_time:.2f} 秒")
                time.sleep(wait_time)


class DataFormatter:
    """数据格式化器"""
    
    @staticmethod
    def format_number(value: Union[int, float, str], precision: int = 2) -> str:
        """格式化数字"""
        try:
            if isinstance(value, str):
                value = float(value)
            return f"{value:.{precision}f}"
        except (ValueError, TypeError):
            return "0.00"
    
    @staticmethod
    def format_percentage(value: Union[int, float, str], precision: int = 2) -> str:
        """格式化百分比"""
        try:
            if isinstance(value, str):
                value = float(value)
            return f"{value:.{precision}f}%"
        except (ValueError, TypeError):
            return "0.00%"
    
    @staticmethod
    def format_timestamp(timestamp: Union[int, float, str]) -> str:
        """格式化时间戳"""
        try:
            if isinstance(timestamp, str):
                timestamp = float(timestamp)
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class ValidationHelper:
    """验证助手"""
    
    @staticmethod
    def is_valid_string(value: Any, max_length: int = 1000) -> bool:
        """验证字符串"""
        if not isinstance(value, str):
            return False
        return len(value.strip()) > 0 and len(value) <= max_length
    
    @staticmethod
    def is_valid_number(value: Any, min_val: Optional[float] = None, max_val: Optional[float] = None) -> bool:
        """验证数字"""
        try:
            num = float(value)
            if min_val is not None and num < min_val:
                return False
            if max_val is not None and num > max_val:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def sanitize_input(value: str, max_length: int = 1000) -> str:
        """清理输入"""
        if not isinstance(value, str):
            return ""
        
        cleaned = value.strip()
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
        
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '|', '`', '$']
        for char in dangerous_chars:
            cleaned = cleaned.replace(char, '')
        
        return cleaned


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
    
    def start_timer(self, operation: str) -> str:
        """开始计时"""
        timer_id = f"{operation}_{time.time()}"
        return timer_id
    
    def end_timer(self, timer_id: str) -> float:
        """结束计时"""
        try:
            operation = timer_id.split('_')[0]
            start_time = float(timer_id.split('_', 1)[1])
            duration = time.time() - start_time
            
            if operation not in self.metrics:
                self.metrics[operation] = []
            
            self.metrics[operation].append(duration)
            
            if len(self.metrics[operation]) > 100:
                self.metrics[operation] = self.metrics[operation][-100:]
            
            return duration
        except (ValueError, IndexError):
            return 0.0
    
    def get_average_time(self, operation: str) -> float:
        """获取平均时间"""
        if operation not in self.metrics or not self.metrics[operation]:
            return 0.0
        return sum(self.metrics[operation]) / len(self.metrics[operation])
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """获取统计信息"""
        stats = {}
        for operation, times in self.metrics.items():
            if times:
                stats[operation] = {
                    'count': len(times),
                    'average': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times),
                    'total': sum(times)
                }
        return stats


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, default_ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        ttl = ttl or self.default_ttl
        self.cache[key] = {
            'value': value,
            'expires': time.time() + ttl
        }
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self.cache:
            return None
        
        item = self.cache[key]
        if time.time() > item['expires']:
            del self.cache[key]
            return None
        
        return item['value']
    
    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
    
    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        now = time.time()
        expired_keys = [key for key, item in self.cache.items() if now > item['expires']]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)


# 全局实例
global_rate_limiter = RateLimiter()
global_performance_monitor = PerformanceMonitor()
global_cache_manager = CacheManager()
