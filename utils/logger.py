"""日志配置模块"""
import logging
import sys
import os
import re
from datetime import datetime
from pathlib import Path


class SensitiveDataFilter(logging.Filter):
    """敏感信息过滤器"""
    
    def __init__(self):
        super().__init__()
        # 敏感信息模式
        self.sensitive_patterns = [
            # API密钥模式
            (r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'api_key="***"'),
            (r'api[_-]?secret["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'api_secret="***"'),
            (r'secret["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'secret="***"'),
            
            # Token模式
            (r'token["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'token="***"'),
            (r'bot[_-]?token["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'bot_token="***"'),
            
            # 密码模式
            (r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'password="***"'),
            (r'pwd["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'pwd="***"'),
            
            # 其他敏感信息
            (r'listen[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'listen_key="***"'),
            (r'chat[_-]?id["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'chat_id="***"'),
        ]
    
    def filter(self, record):
        """过滤敏感信息"""
        try:
            if hasattr(record, 'msg') and record.msg:
                msg = str(record.msg)
                
                # 应用所有敏感信息模式
                for pattern, replacement in self.sensitive_patterns:
                    msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
                
                # 检查是否包含明显的API密钥格式（64位十六进制）
                if re.search(r'\b[a-fA-F0-9]{64}\b', msg):
                    msg = re.sub(r'\b[a-fA-F0-9]{64}\b', '***', msg)
                
                # 检查是否包含Bot Token格式（数字:字母数字）
                if re.search(r'\b\d+:[A-Za-z0-9_-]{35}\b', msg):
                    msg = re.sub(r'\b\d+:[A-Za-z0-9_-]{35}\b', '***', msg)
                
                record.msg = msg
            
            if hasattr(record, 'args') and record.args:
                # 处理格式化参数中的敏感信息
                filtered_args = []
                for arg in record.args:
                    if isinstance(arg, str):
                        filtered_arg = arg
                        for pattern, replacement in self.sensitive_patterns:
                            filtered_arg = re.sub(pattern, replacement, filtered_arg, flags=re.IGNORECASE)
                        filtered_args.append(filtered_arg)
                    else:
                        filtered_args.append(arg)
                record.args = tuple(filtered_args)
                
        except Exception as e:
            # 如果过滤过程出错，记录错误但不影响日志输出
            print(f"敏感信息过滤出错: {e}")
        
        return True


def setup_logger(name: str = 'binance_monitor', level: int = logging.INFO) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        
    Returns:
        配置好的日志记录器
    """
    # 从环境变量读取日志级别
    env_level = os.getenv('BINANCE_LOG_LEVEL', '').upper()
    if env_level == 'DEBUG':
        level = logging.DEBUG
    elif env_level == 'WARNING':
        level = logging.WARNING
    elif env_level == 'ERROR':
        level = logging.ERROR
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 清除已有的处理器
    logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # 创建日志目录
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # 文件处理器 - 保存到 logs/ 目录
    log_filename = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(level)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # 添加敏感信息过滤器
    sensitive_filter = SensitiveDataFilter()
    console_handler.addFilter(sensitive_filter)
    file_handler.addFilter(sensitive_filter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
