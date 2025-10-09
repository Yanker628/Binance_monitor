"""日志配置模块"""
import logging
import sys
import os
import re
from datetime import datetime
from pathlib import Path


class SensitiveDataFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.sensitive_patterns = [
            (r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'api_key="***"'),
            (r'api[_-]?secret["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'api_secret="***"'),
            (r'secret["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'secret="***"'),
            (r'token["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'token="***"'),
            (r'bot[_-]?token["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'bot_token="***"'),
            (r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'password="***"'),
            (r'pwd["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'pwd="***"'),
            (r'listen[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'listen_key="***"'),
            (r'chat[_-]?id["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'chat_id="***"'),
        ]
    
    def filter(self, record):
        try:
            if hasattr(record, 'msg') and record.msg:
                msg = str(record.msg)
                
                for pattern, replacement in self.sensitive_patterns:
                    msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
                
                if re.search(r'\b[a-fA-F0-9]{64}\b', msg):
                    msg = re.sub(r'\b[a-fA-F0-9]{64}\b', '***', msg)
                
                if re.search(r'\b\d+:[A-Za-z0-9_-]{35}\b', msg):
                    msg = re.sub(r'\b\d+:[A-Za-z0-9_-]{35}\b', '***', msg)
                
                record.msg = msg
            
            if hasattr(record, 'args') and record.args:
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
            print(f"敏感信息过滤出错: {e}")
        
        return True


def setup_logger(name: str = 'binance_monitor', level: int = logging.INFO) -> logging.Logger:
    env_level = os.getenv('BINANCE_LOG_LEVEL', '').upper()
    if env_level == 'DEBUG':
        level = logging.DEBUG
    elif env_level == 'WARNING':
        level = logging.WARNING
    elif env_level == 'ERROR':
        level = logging.ERROR
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    log_filename = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(level)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    sensitive_filter = SensitiveDataFilter()
    console_handler.addFilter(sensitive_filter)
    file_handler.addFilter(sensitive_filter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
