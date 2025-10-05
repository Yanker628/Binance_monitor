"""多 Telegram Bot 管理器"""
import logging
from typing import List, Optional
from .bot import TelegramBot

# 使用主程序的 logger
logger = logging.getLogger('binance_monitor')


class MultiBotManager:
    """多 Telegram Bot 管理器
    
    支持同时向多个 Bot 发送消息
    """
    
    def __init__(self, bot_configs: List[tuple]):
        """
        初始化多 Bot 管理器
        
        Args:
            bot_configs: [(token1, chat_id1, topic_id1), (token2, chat_id2, topic_id2), ...]
                         topic_id 可选，为 None 表示不使用话题
        """
        self.bots: List[TelegramBot] = []
        
        for i, config in enumerate(bot_configs, 1):
            if len(config) == 2:
                token, chat_id = config
                topic_id = None
            elif len(config) == 3:
                token, chat_id, topic_id = config
            else:
                logger.warning(f"⚠️  Bot #{i} 配置格式错误，跳过")
                continue
            
            if token and chat_id:
                bot = TelegramBot(token, chat_id, topic_id)
                self.bots.append(bot)
                logger.info(f"✅ Bot #{i} 已注册" + (f" (Topic: {topic_id})" if topic_id else ""))
            else:
                logger.warning(f"⚠️  Bot #{i} 配置不完整，跳过")
        
        if not self.bots:
            raise ValueError("至少需要配置一个 Telegram Bot")
        
        logger.info(f"📱 多 Bot 管理器已初始化，共 {len(self.bots)} 个 Bot")
    
    def send_message_sync(self, message: str, parse_mode: str = 'HTML'):
        """
        同步发送消息到所有 Bot
        
        Args:
            message: 消息内容
            parse_mode: 解析模式（HTML/Markdown）
        
        Returns:
            bool: 至少一个 Bot 发送成功则返回 True
        """
        success_count = 0
        fail_count = 0
        
        for i, bot in enumerate(self.bots, 1):
            try:
                logger.debug(f"[Bot #{i}] 开始发送消息...")
                result = bot.send_message_sync(message, parse_mode)
                if result:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"[Bot #{i}] 发送异常: {e}")
                fail_count += 1
        
        # 汇总日志
        if success_count > 0:
            logger.info(
                f"[多Bot] ✅ 消息发送完成: "
                f"成功 {success_count}/{len(self.bots)}"
                + (f", 失败 {fail_count}" if fail_count > 0 else "")
            )
            return True
        else:
            logger.error(f"[多Bot] ❌ 所有 Bot 发送失败 ({len(self.bots)}/{len(self.bots)})")
            return False
    
    def get_bot_count(self) -> int:
        """获取 Bot 数量"""
        return len(self.bots)

