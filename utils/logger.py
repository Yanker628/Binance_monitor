"""日志配置模块"""
import logging
import sys
import os
from datetime import datetime
from pathlib import Path


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
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
