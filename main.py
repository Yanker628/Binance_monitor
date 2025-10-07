"""币安合约监控主程序"""
import time
import threading
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict

from config import Settings
from binance import BinanceClient, UserDataStreamWebSocket
from monitor import PositionMonitor
from notifier import TelegramBot, MultiBotManager
from notifier.aggregator import MessageAggregator
from utils.formatter import (
    format_open_position_message,
    format_close_position_message,
    format_increase_position_message,
    format_decrease_position_message
)
from utils.logger import setup_logger

# 设置日志（使用配置文件中的日志级别）
logger = setup_logger('binance_monitor', Settings.get_log_level())


class BinanceMonitorApp:
    """币安合约监控应用"""
    
    def __init__(self):
        # 验证配置
        Settings.validate()
        
        # 初始化账户集合
        self.accounts: List[Dict] = []
        self._multi_account = False
        
        # 标准合约账户（可选）
        if Settings.BINANCE_FUTURES_ENABLED:
            futures_client = BinanceClient(
                Settings.BINANCE_API_KEY,
                Settings.BINANCE_API_SECRET,
                Settings.BINANCE_API_URL
            )
            self._register_account(
                account_name="合约账户",
                client=futures_client,
                ws_base_url=Settings.BINANCE_WS_URL,
                listen_endpoint='/v1/listenKey'
            )
        
        # 统一账户（可选）
        if Settings.BINANCE_UNIFIED_ENABLED:
            unified_client = BinanceClient(
                Settings.BINANCE_UNIFIED_API_KEY,
                Settings.BINANCE_UNIFIED_API_SECRET,
                Settings.BINANCE_UNIFIED_API_URL
            )
            self._register_account(
                account_name="统一账户",
                client=unified_client,
                ws_base_url=Settings.BINANCE_UNIFIED_WS_URL,
                listen_endpoint=Settings.BINANCE_UNIFIED_LISTEN_KEY_ENDPOINT
            )
        
        self._multi_account = len(self.accounts) > 1
        
        # 初始化 Telegram Bot
        bot_configs = [
            (Settings.TELEGRAM_BOT_TOKEN, Settings.TELEGRAM_CHAT_ID, Settings.TELEGRAM_TOPIC_ID),
        ]
        
        if Settings.TELEGRAM_BOT_TOKEN_2 and Settings.TELEGRAM_CHAT_ID_2:
            bot_configs.append((Settings.TELEGRAM_BOT_TOKEN_2, Settings.TELEGRAM_CHAT_ID_2, Settings.TELEGRAM_TOPIC_ID_2))
        
        self.telegram = MultiBotManager(bot_configs)
        
        # 创建后台事件循环（用于聚合器）
        self.event_loop = None
        self.loop_thread = None
        
        # 初始化消息聚合器（使用配置的聚合窗口）
        self.aggregator = MessageAggregator(
            send_callback=self.telegram.send_message_sync,
            window_ms=Settings.MESSAGE_AGGREGATION_WINDOW_MS
        )
        
        self.is_running = False
        
    def _register_account(self, account_name: str, client: BinanceClient, ws_base_url: str, listen_endpoint: str):
        monitor = PositionMonitor()
        self._attach_callbacks(monitor, account_name)
        logger.info(f"📝 注册账户 [{account_name}] WS_URL: {ws_base_url}")
        account = {
            'name': account_name,
            'client': client,
            'monitor': monitor,
            'ws_base_url': ws_base_url.rstrip('/'),
            'listen_endpoint': listen_endpoint,
            'listen_key': '',
            'ws': None,
            'keepalive_thread': None
        }
        self.accounts.append(account)
    
    def _attach_callbacks(self, monitor: PositionMonitor, account_name: str):
        """为指定账户监控器绑定事件回调"""
        
        def send_with_account_prefix(message: str):
            """添加账户前缀（仅多账户模式）"""
            if self._multi_account:
                message = f"👤 <b>{account_name}</b>\n\n" + message
            self.telegram.send_message_sync(message)
        
        def _create_position_data(position, old_position=None):
            """创建仓位数据字典供聚合器使用"""
            data = {
                'symbol': position.symbol,
                'position_side': position.position_side,
                'position_amt': position.position_amt,
                'entry_price': position.entry_price,
                'mark_price': position.mark_price,
                'unrealized_pnl': position.unrealized_pnl,
                'leverage': position.leverage,
                'notional': position.notional,
                'isolated': position.isolated,
                'previous_amount': old_position.position_amt if old_position else 0,
                'old_entry_price': old_position.entry_price if old_position else position.entry_price,
                'old_unrealized_pnl': old_position.unrealized_pnl if old_position else 0
            }
            return data
        
        def on_open(position):
            notional = abs(position.notional)
            logger.info(
                f"[{account_name}] ✅ 开仓 {position.symbol} {position.get_side()} "
                f"{abs(position.position_amt):.4f}币 @ {position.entry_price:.4f} "
                f"= {notional:.2f} USDT"
            )
            position_data = _create_position_data(position)
            self.aggregator.add_position_change(position_data, 'OPEN', None)
        
        def on_close(position):
            key = monitor._get_position_key(position.symbol, position.position_side)
            order_pnl_data = getattr(monitor, 'order_pnl_cache', {}).get(key)
            
            if order_pnl_data:
                actual_pnl = order_pnl_data['actual_pnl']
                close_price = order_pnl_data['close_price']
                close_notional = order_pnl_data.get('total_cost', order_pnl_data['quantity'] * close_price)
                pnl_sign = "+" if actual_pnl >= 0 else ""
                logger.info(
                    f"[{account_name}] ❌ 平仓 {position.symbol} {position.get_side()} 实际盈亏: {pnl_sign}{actual_pnl:.2f} USDT"
                )
            else:
                actual_pnl = position.unrealized_pnl
                close_price = position.mark_price
                close_notional = abs(position.position_amt * position.mark_price) if position.position_amt != 0 else 0
                pnl_sign = "+" if actual_pnl >= 0 else ""
                logger.info(
                    f"[{account_name}] ❌ 平仓 {position.symbol} {position.get_side()} 盈亏: {pnl_sign}{actual_pnl:.2f} USDT"
                )
            
            position_data = {
                'symbol': position.symbol,
                'position_side': position.position_side,
                'position_amt': 0,
                'entry_price': position.entry_price,
                'mark_price': position.mark_price,
                'unrealized_pnl': actual_pnl,
                'leverage': position.leverage,
                'notional': position.notional,
                'isolated': position.isolated,
                'previous_amount': position.position_amt,
                'previous_side': position.get_side(),
                'old_entry_price': position.entry_price,
                'old_unrealized_pnl': position.unrealized_pnl,
                'close_price': close_price,
                'close_notional': close_notional,
                'actual_pnl': actual_pnl
            }
            self.aggregator.add_position_change(position_data, 'CLOSE', position)
        
        def on_increase(new_position, old_position):
            increase_amt = abs(new_position.position_amt) - abs(old_position.position_amt)
            old_notional = abs(old_position.notional)
            new_notional = abs(new_position.notional)
            increase_value = new_notional - old_notional
            logger.info(
                f"[{account_name}] ➕ 加仓 {new_position.symbol} +{increase_amt:.4f}币 @ {new_position.entry_price:.4f} "
                f"仓位: {old_notional:.2f} → {new_notional:.2f} USDT (+{increase_value:.2f})"
            )
            position_data = _create_position_data(new_position, old_position)
            self.aggregator.add_position_change(position_data, 'ADD', old_position)
        
        def on_decrease(new_position, old_position):
            decrease_amt = abs(old_position.position_amt) - abs(new_position.position_amt)
            old_notional = abs(old_position.notional)
            new_notional = abs(new_position.notional)
            decrease_value = old_notional - new_notional
            logger.info(
                f"[{account_name}] ➖ 减仓 {new_position.symbol} -{decrease_amt:.4f}币 "
                f"仓位: {old_notional:.2f} → {new_notional:.2f} USDT (-{decrease_value:.2f})"
            )
            position_data = _create_position_data(new_position, old_position)
            self.aggregator.add_position_change(position_data, 'REDUCE', old_position)
        
        monitor.on_position_opened = on_open
        monitor.on_position_closed = on_close
        monitor.on_position_increased = on_increase
        monitor.on_position_decreased = on_decrease
    
    def _init_positions(self):
        """初始化仓位信息"""
        pass
    
    def _start_user_data_streams(self):
        """启动所有账户的用户数据流"""
        for account in self.accounts:
            client: BinanceClient = account['client']
            listen_endpoint: str = account['listen_endpoint']
            
            logger.info(f"🔑 [{account['name']}] 获取 listenKey: {listen_endpoint}")
            listen_key = client.start_user_data_stream(listen_endpoint)
            account['listen_key'] = listen_key
            logger.info(f"✅ [{account['name']}] listenKey: {listen_key[:20]}...")
            
            ws = UserDataStreamWebSocket(listen_key, account['ws_base_url'])
            monitor: PositionMonitor = account['monitor']
            ws.register_callback('ACCOUNT_UPDATE', monitor.handle_account_update)
            ws.register_callback('ORDER_TRADE_UPDATE', monitor.handle_order_update)
            logger.info(f"📡 [{account['name']}] 注册回调: ACCOUNT_UPDATE, ORDER_TRADE_UPDATE")
            ws.connect()
            account['ws'] = ws
            logger.info(f"✅ [{account['name']}] WebSocket 连接成功")
            
            self._start_keepalive_thread(account)
    
    def _start_keepalive_thread(self, account: Dict):
        """为指定账户启动listenKey保活线程"""
        def keepalive():
            client: BinanceClient = account['client']
            listen_endpoint: str = account['listen_endpoint']
            keepalive_interval = Settings.LISTEN_KEY_KEEPALIVE_INTERVAL
            logger.info(f"[{account['name']}] listenKey保活间隔: {keepalive_interval}秒 ({keepalive_interval/60:.1f}分钟)")
            while self.is_running:
                time.sleep(keepalive_interval)
                if self.is_running and account['listen_key']:
                    try:
                        client.keepalive_user_data_stream(account['listen_key'], listen_endpoint)
                        logger.info(f"[{account['name']}] ✅ listenKey保活成功")
                    except Exception as e:
                        logger.error(f"[{account['name']}] ❌ listenKey保活失败: {e}")
        
        thread = threading.Thread(target=keepalive, daemon=True)
        thread.start()
        account['keepalive_thread'] = thread
    
    def _start_telegram_bot(self):
        """初始化Telegram Bot"""
        pass
    
    def _start_event_loop(self):
        """在后台线程中启动事件循环"""
        def run_loop():
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            logger.info("✅ 后台事件循环已启动")
            self.event_loop.run_forever()
        
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        time.sleep(0.1)  # 等待事件循环启动
    
    def _stop_event_loop(self):
        """停止后台事件循环"""
        if self.event_loop:
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)
            logger.info("⛔ 后台事件循环已停止")
    
    def start(self):
        """启动监控"""
        try:
            enabled_accounts = [acc['name'] for acc in self.accounts]
            logger.info(
                f"🚀 币安合约监控启动 (测试网: {Settings.BINANCE_TESTNET}) | 账户: {', '.join(enabled_accounts)}"
            )
            self.is_running = True
            
            # 启动后台事件循环（用于聚合器）
            self._start_event_loop()
            
            # 将事件循环设置到聚合器中
            self.aggregator.event_loop = self.event_loop
            
            self._init_positions()
            self._start_user_data_streams()
            self._start_telegram_bot()
            
            account_text = "、".join(enabled_accounts)
            self.telegram.send_message_sync(
                "✅ <b>币安合约监控已启动</b>\n\n"
                f"监听账户: {account_text}\n"
                "将自动推送: 开仓/加仓/减仓/平仓通知"
            )
            
            logger.info("✅ 监控已启动")
            
            while self.is_running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.error(f"运行出错: {e}", exc_info=True)
            self.stop()
    
    def stop(self):
        """停止监控"""
        self.is_running = False
        
        # 停止后台事件循环
        self._stop_event_loop()
        
        for account in self.accounts:
            ws: Optional[UserDataStreamWebSocket] = account.get('ws')
            if ws:
                ws.close()
            listen_key = account.get('listen_key')
            if listen_key:
                try:
                    account['client'].close_user_data_stream(listen_key, account['listen_endpoint'])
                except Exception as e:
                    logger.error(f"[{account['name']}] 关闭listenKey失败: {e}")
        try:
            self.telegram.send_message_sync("⛔ <b>币安合约监控已停止</b>")
        except Exception as e:
            logger.error(f"发送停止通知失败: {e}")
        logger.info("⛔ 监控已停止")


def main():
    """主函数"""
    try:
        app = BinanceMonitorApp()
        app.start()
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)


if __name__ == "__main__":
    main()
