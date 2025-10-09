"""配置管理模块 - 已升级为安全版本"""
import logging
from typing import Optional
from .secure_settings import secure_settings

# 使用安全配置管理
logger = logging.getLogger('binance_monitor')


class Settings:
    """应用配置 - 兼容性包装器"""
    
    # 币安标准合约账户配置
    @property
    def BINANCE_API_KEY(self) -> str:
        return secure_settings.get_binance_api_key('futures')
    
    @property
    def BINANCE_API_SECRET(self) -> str:
        return secure_settings.get_binance_api_secret('futures')
    
    @property
    def BINANCE_TESTNET(self) -> bool:
        return secure_settings.binance_testnet
    
    @property
    def BINANCE_FUTURES_ENABLED(self) -> bool:
        return secure_settings.binance_futures_enabled
    
    @property
    def BINANCE_API_URL(self) -> str:
        return secure_settings.binance_api_url
    
    @property
    def BINANCE_WS_URL(self) -> str:
        return secure_settings.binance_ws_url
    
    # 币安统一账户配置
    @property
    def BINANCE_UNIFIED_ENABLED(self) -> bool:
        return secure_settings.binance_unified_enabled
    
    @property
    def BINANCE_UNIFIED_API_KEY(self) -> str:
        return secure_settings.get_binance_api_key('unified')
    
    @property
    def BINANCE_UNIFIED_API_SECRET(self) -> str:
        return secure_settings.get_binance_api_secret('unified')
    
    @property
    def BINANCE_UNIFIED_API_URL(self) -> str:
        return secure_settings.binance_unified_api_url
    
    @property
    def BINANCE_UNIFIED_WS_URL(self) -> str:
        return secure_settings.binance_unified_ws_url
    
    @property
    def BINANCE_UNIFIED_LISTEN_KEY_ENDPOINT(self) -> str:
        return secure_settings.binance_unified_listen_key_endpoint

    # Telegram 配置（支持多个 Bot）
    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        return secure_settings.get_telegram_config()[0]
    
    @property
    def TELEGRAM_CHAT_ID(self) -> str:
        return secure_settings.get_telegram_config()[1]
    
    @property
    def TELEGRAM_TOPIC_ID(self) -> Optional[int]:
        return secure_settings.telegram_topic_id
    
    @property
    def TELEGRAM_BOT_TOKEN_2(self) -> str:
        config_2 = secure_settings.get_telegram_config_2()
        return config_2[0] if config_2 else ''
    
    @property
    def TELEGRAM_CHAT_ID_2(self) -> str:
        config_2 = secure_settings.get_telegram_config_2()
        return config_2[1] if config_2 else ''
    
    @property
    def TELEGRAM_TOPIC_ID_2(self) -> Optional[int]:
        return secure_settings.telegram_topic_id_2
    
    # 应用配置
    @property
    def LOG_LEVEL(self) -> str:
        return secure_settings.log_level
    
    @property
    def MESSAGE_AGGREGATION_WINDOW_MS(self) -> int:
        return secure_settings.message_aggregation_window_ms
    
    @property
    def LISTEN_KEY_KEEPALIVE_INTERVAL(self) -> int:
        return secure_settings.listen_key_keepalive_interval
    
    @classmethod
    def get_log_level(cls) -> int:
        """获取日志级别常量"""
        return secure_settings.get_log_level()
    
    @classmethod
    def validate(cls) -> bool:
        """验证所有配置"""
        return secure_settings.validate_all_config()
