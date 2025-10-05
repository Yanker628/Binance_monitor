"""配置管理模块"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Settings:
    """应用配置"""
    
    # 币安标准合约账户配置
    BINANCE_API_KEY: str = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET: str = os.getenv('BINANCE_API_SECRET', '')
    BINANCE_TESTNET: bool = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
    BINANCE_FUTURES_ENABLED: bool = os.getenv('BINANCE_FUTURES_ENABLED', 'True').lower() == 'true'
    
    BINANCE_API_URL: str = (
        'https://testnet.binancefuture.com/fapi'
        if BINANCE_TESTNET
        else 'https://fapi.binance.com/fapi'
    )
    
    BINANCE_WS_URL: str = (
        'wss://stream.binancefuture.com/ws'
        if BINANCE_TESTNET
        else 'wss://fstream.binance.com/ws'
    )
    
    # 币安统一账户配置
    BINANCE_UNIFIED_ENABLED: bool = os.getenv('BINANCE_UNIFIED_ENABLED', 'False').lower() == 'true'
    BINANCE_UNIFIED_API_KEY: str = os.getenv('BINANCE_UNIFIED_API_KEY', '')
    BINANCE_UNIFIED_API_SECRET: str = os.getenv('BINANCE_UNIFIED_API_SECRET', '')
    BINANCE_UNIFIED_API_URL: str = 'https://papi.binance.com'
    BINANCE_UNIFIED_WS_URL: str = 'wss://fstream.binance.com/pm/ws'
    BINANCE_UNIFIED_LISTEN_KEY_ENDPOINT: str = '/papi/v1/listenKey'

    # Telegram 配置（支持多个 Bot）
    # 主 Bot（必填）
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')
    TELEGRAM_TOPIC_ID: Optional[int] = int(os.getenv('TELEGRAM_TOPIC_ID', '0')) or None
    
    # 第二个 Bot（可选）
    TELEGRAM_BOT_TOKEN_2: str = os.getenv('TELEGRAM_BOT_TOKEN_2', '')
    TELEGRAM_CHAT_ID_2: str = os.getenv('TELEGRAM_CHAT_ID_2', '')
    TELEGRAM_TOPIC_ID_2: Optional[int] = int(os.getenv('TELEGRAM_TOPIC_ID_2', '0')) or None
    
    # 应用配置
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO').upper()
    MESSAGE_AGGREGATION_WINDOW_MS: int = int(os.getenv('MESSAGE_AGGREGATION_WINDOW_MS', '1000'))
    LISTEN_KEY_KEEPALIVE_INTERVAL: int = int(os.getenv('LISTEN_KEY_KEEPALIVE_INTERVAL', '1200'))  # 20分钟
    
    @classmethod
    def get_log_level(cls) -> int:
        """获取日志级别常量"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(cls.LOG_LEVEL, logging.INFO)
    
    @classmethod
    def validate(cls) -> bool:
        if cls.BINANCE_FUTURES_ENABLED:
            if not cls.BINANCE_API_KEY or not cls.BINANCE_API_SECRET:
                raise ValueError("请设置BINANCE_API_KEY和BINANCE_API_SECRET")
        if not cls.TELEGRAM_BOT_TOKEN or not cls.TELEGRAM_CHAT_ID:
            raise ValueError("请设置TELEGRAM_BOT_TOKEN和TELEGRAM_CHAT_ID")
        if cls.BINANCE_UNIFIED_ENABLED:
            if not cls.BINANCE_UNIFIED_API_KEY or not cls.BINANCE_UNIFIED_API_SECRET:
                raise ValueError("请设置BINANCE_UNIFIED_API_KEY和BINANCE_UNIFIED_API_SECRET")
        if not cls.BINANCE_FUTURES_ENABLED and not cls.BINANCE_UNIFIED_ENABLED:
            raise ValueError("请至少启用一个账户来源（合约或统一账户）")
        return True
