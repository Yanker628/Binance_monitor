"""Telegram Bot模块"""
import logging
import requests
from typing import Optional

logger = logging.getLogger('binance_monitor')


class TelegramBot:
    """Telegram Bot推送类"""
    
    def __init__(self, token: str, chat_id: str, topic_id: Optional[int] = None):
        self.api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id
        self.topic_id = topic_id
        logger.info(f"📱 Telegram Bot 已初始化，Chat ID: {chat_id}" + (f", Topic ID: {topic_id}" if topic_id else ""))
    
    def send_message_sync(self, message: str, parse_mode: str = 'HTML'):
        try:
            logger.debug(f"[Telegram] 准备发送消息，长度: {len(message)} 字符")
            
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            if self.topic_id:
                data['message_thread_id'] = str(self.topic_id)
            
            response = requests.post(
                self.api_url,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"[Telegram] ✅ 消息发送成功" + (f" (Topic: {self.topic_id})" if self.topic_id else ""))
                return True
            else:
                error_msg = response.json().get('description', 'Unknown error')
                logger.error(f"[Telegram] ❌ 发送失败: {error_msg}")
                logger.error(f"[Telegram] Response: {response.text}")
                return False
        except Exception as e:
            logger.error(f"[Telegram] ❌ 发送异常: {e}", exc_info=True)
            return False
