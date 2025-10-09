"""安全配置管理模块"""
import os
import re
import logging
from typing import Optional
from dotenv import load_dotenv
import hashlib
import base64

# 加载环境变量
load_dotenv()

logger = logging.getLogger('binance_monitor')


class SecureSettings:
    """安全配置管理类"""
    
    def __init__(self):
        self._api_keys = {}
        self._secrets = {}
        self._load_and_validate_config()
    
    def _load_and_validate_config(self):
        """加载并验证配置"""
        # 币安标准合约账户配置
        if os.getenv('BINANCE_FUTURES_ENABLED', 'True').lower() == 'true':
            api_key = self._get_secure_env('BINANCE_API_KEY')
            api_secret = self._get_secure_env('BINANCE_API_SECRET')
            
            if not self._validate_binance_credentials(api_key, api_secret):
                raise ValueError("BINANCE_API_KEY 或 BINANCE_API_SECRET 格式无效")
            
            self._api_keys['futures'] = api_key
            self._secrets['futures'] = api_secret
        
        # 币安统一账户配置
        if os.getenv('BINANCE_UNIFIED_ENABLED', 'False').lower() == 'true':
            api_key = self._get_secure_env('BINANCE_UNIFIED_API_KEY')
            api_secret = self._get_secure_env('BINANCE_UNIFIED_API_SECRET')
            
            if not self._validate_binance_credentials(api_key, api_secret):
                raise ValueError("BINANCE_UNIFIED_API_KEY 或 BINANCE_UNIFIED_API_SECRET 格式无效")
            
            self._api_keys['unified'] = api_key
            self._secrets['unified'] = api_secret
        
        # Telegram配置
        self.telegram_token = self._get_secure_env('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = self._get_secure_env('TELEGRAM_CHAT_ID')
        
        if not self._validate_telegram_config(self.telegram_token, self.telegram_chat_id):
            raise ValueError("TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 格式无效")
        
        # 可选第二个Bot
        self.telegram_token_2 = self._get_secure_env('TELEGRAM_BOT_TOKEN_2', required=False)
        self.telegram_chat_id_2 = self._get_secure_env('TELEGRAM_CHAT_ID_2', required=False)
        
        if self.telegram_token_2 and not self._validate_telegram_config(self.telegram_token_2, self.telegram_chat_id_2):
            raise ValueError("TELEGRAM_BOT_TOKEN_2 或 TELEGRAM_CHAT_ID_2 格式无效")
    
    def _get_secure_env(self, key: str, required: bool = True) -> str:
        """安全获取环境变量"""
        value = os.getenv(key, '')
        
        if required and not value:
            raise ValueError(f"环境变量 {key} 未设置")
        
        if value:
            # 记录配置加载（不记录敏感值）
            logger.info(f"✅ 已加载配置: {key}")
        
        return value
    
    def _validate_binance_credentials(self, api_key: str, api_secret: str) -> bool:
        """验证币安API凭证格式"""
        if not api_key or not api_secret:
            return False
        
        if len(api_key.strip()) < 8 or len(api_secret.strip()) < 8:
            logger.error(f"API Key/Secret长度不足: {len(api_key)}/{len(api_secret)}")
            return False
        
        # 检查是否为空字符串或只有空格
        if not api_key.strip() or not api_secret.strip():
            logger.error("API Key/Secret不能为空")
            return False
        
        logger.info(f"✅ API凭证验证通过: Key长度={len(api_key)}, Secret长度={len(api_secret)}")
        return True
    
    def _validate_telegram_config(self, token: str, chat_id: str) -> bool:
        """验证Telegram配置格式"""
        if not token or not chat_id:
            return False
        
        # Telegram Bot Token格式验证
        if not re.match(r'^\d+:[A-Za-z0-9_-]{35}$', token):
            logger.error(f"Telegram Bot Token格式无效: {token[:10]}...")
            return False
        
        # Chat ID格式验证（可以是数字或负数）
        if not re.match(r'^-?\d+$', chat_id):
            logger.error(f"Chat ID格式无效: {chat_id}")
            return False
        
        return True
    
    def get_binance_api_key(self, account_type: str = 'futures') -> str:
        """获取币安API Key"""
        if account_type not in self._api_keys:
            raise ValueError(f"未配置 {account_type} 账户的API Key")
        return self._api_keys[account_type]
    
    def get_binance_api_secret(self, account_type: str = 'futures') -> str:
        """获取币安API Secret"""
        if account_type not in self._secrets:
            raise ValueError(f"未配置 {account_type} 账户的API Secret")
        return self._secrets[account_type]
    
    def get_telegram_config(self) -> tuple:
        """获取Telegram配置"""
        return self.telegram_token, self.telegram_chat_id
    
    def get_telegram_config_2(self) -> Optional[tuple]:
        """获取第二个Telegram配置"""
        if self.telegram_token_2 and self.telegram_chat_id_2:
            return self.telegram_token_2, self.telegram_chat_id_2
        return None
    
    def validate_all_config(self) -> bool:
        """验证所有配置"""
        try:
            # 检查是否至少有一个账户配置
            if not self._api_keys:
                raise ValueError("请至少启用一个账户来源（合约或统一账户）")
            
            logger.info("✅ 所有配置验证通过")
            return True
        except Exception as e:
            logger.error(f"❌ 配置验证失败: {e}")
            return False
    
    # 其他配置项
    @property
    def binance_testnet(self) -> bool:
        return os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
    
    @property
    def binance_futures_enabled(self) -> bool:
        return 'futures' in self._api_keys
    
    @property
    def binance_unified_enabled(self) -> bool:
        return 'unified' in self._api_keys
    
    @property
    def binance_api_url(self) -> str:
        return (
            'https://testnet.binancefuture.com/fapi'
            if self.binance_testnet
            else 'https://fapi.binance.com/fapi'
        )
    
    @property
    def binance_ws_url(self) -> str:
        return (
            'wss://stream.binancefuture.com/ws'
            if self.binance_testnet
            else 'wss://fstream.binance.com/ws'
        )
    
    @property
    def binance_unified_api_url(self) -> str:
        return 'https://papi.binance.com'
    
    @property
    def binance_unified_ws_url(self) -> str:
        return 'wss://fstream.binance.com/pm/ws'
    
    @property
    def binance_unified_listen_key_endpoint(self) -> str:
        return '/papi/v1/listenKey'
    
    @property
    def telegram_topic_id(self) -> Optional[int]:
        topic_id = os.getenv('TELEGRAM_TOPIC_ID', '0')
        return int(topic_id) if topic_id != '0' else None
    
    @property
    def telegram_topic_id_2(self) -> Optional[int]:
        topic_id = os.getenv('TELEGRAM_TOPIC_ID_2', '0')
        return int(topic_id) if topic_id != '0' else None
    
    @property
    def log_level(self) -> str:
        return os.getenv('LOG_LEVEL', 'INFO').upper()
    
    @property
    def message_aggregation_window_ms(self) -> int:
        return int(os.getenv('MESSAGE_AGGREGATION_WINDOW_MS', '1000'))
    
    @property
    def listen_key_keepalive_interval(self) -> int:
        return int(os.getenv('LISTEN_KEY_KEEPALIVE_INTERVAL', '1200'))
    
    def get_log_level(self) -> int:
        """获取日志级别常量"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(self.log_level, logging.INFO)


# 创建全局实例
secure_settings = SecureSettings()
