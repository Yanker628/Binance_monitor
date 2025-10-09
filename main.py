"""币安合约监控主程序"""
import time
import threading
import asyncio
import logging
import signal
import sys
import os
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

logger = setup_logger('binance_monitor', Settings.get_log_level())


class BinanceMonitorApp:
    """币安合约监控应用"""
    
    def __init__(self):
        self._setup_signal_handlers()
        Settings.validate()
        
        self.accounts: List[Dict] = []
        self._multi_account = False
        
        if Settings().BINANCE_FUTURES_ENABLED:
            futures_client = BinanceClient(
                Settings().BINANCE_API_KEY,
                Settings().BINANCE_API_SECRET,
                Settings().BINANCE_API_URL
            )
            self._register_account(
                account_name="合约账户",
                client=futures_client,
                ws_base_url=Settings().BINANCE_WS_URL,
                listen_endpoint='/v1/listenKey'
            )
        
        if Settings().BINANCE_UNIFIED_ENABLED:
            unified_client = BinanceClient(
                Settings().BINANCE_UNIFIED_API_KEY,
                Settings().BINANCE_UNIFIED_API_SECRET,
                Settings().BINANCE_UNIFIED_API_URL
            )
            self._register_account(
                account_name="统一账户",
                client=unified_client,
                ws_base_url=Settings().BINANCE_UNIFIED_WS_URL,
                listen_endpoint=Settings().BINANCE_UNIFIED_LISTEN_KEY_ENDPOINT
            )
        
        self._multi_account = len(self.accounts) > 1
        
        settings_instance = Settings()
        bot_configs = [
            (settings_instance.TELEGRAM_BOT_TOKEN, settings_instance.TELEGRAM_CHAT_ID, settings_instance.TELEGRAM_TOPIC_ID),
        ]
        
        if settings_instance.TELEGRAM_BOT_TOKEN_2 and settings_instance.TELEGRAM_CHAT_ID_2:
            bot_configs.append((settings_instance.TELEGRAM_BOT_TOKEN_2, settings_instance.TELEGRAM_CHAT_ID_2, settings_instance.TELEGRAM_TOPIC_ID_2))
        
        self.telegram = MultiBotManager(bot_configs)
        
        self.event_loop = None
        self.loop_thread = None
        
        self.aggregator = MessageAggregator(
            send_callback=self.telegram.send_message_sync,
            window_ms=settings_instance.MESSAGE_AGGREGATION_WINDOW_MS,
            event_loop=None
        )
        
        self.is_running = False
        self.restart_requested = False
        
    def _setup_signal_handlers(self):
        """设置信号处理器，支持优雅重启"""
        def signal_handler(signum, frame):
            if signum == signal.SIGUSR1:
                logger.info("🔄 收到重启信号，准备优雅重启...")
                self.restart_requested = True
                self.stop()
            elif signum == signal.SIGTERM:
                logger.info("⛔ 收到停止信号，准备优雅停止...")
                self.stop()
        
        signal.signal(signal.SIGUSR1, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
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
            if self._multi_account:
                message = f"👤 <b>{account_name}</b>\n\n" + message
            self.telegram.send_message_sync(message)
        
        def _create_position_data(position, old_position=None):
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
        
        def on_close(position, order_cache=None):
            key = monitor._get_position_key(position.symbol, position.position_side)
            
            # 优先使用传入的订单缓存数据
            if order_cache:
                actual_pnl = order_cache['actual_pnl']
                close_price = order_cache['close_price']
                close_notional = order_cache.get('total_cost', order_cache['quantity'] * close_price)
                logger.info(f"[{account_name}] ❌ 平仓 {position.symbol} {position.get_side()} 使用传入订单缓存盈亏: {actual_pnl:.2f} USDT")
            else:
                # 回退到从monitor获取
                order_pnl_data = getattr(monitor, 'order_pnl_cache', {}).get(key)
                if order_pnl_data:
                    actual_pnl = order_pnl_data['actual_pnl']
                    close_price = order_pnl_data['close_price']
                    close_notional = order_pnl_data.get('total_cost', order_pnl_data['quantity'] * close_price)
                    logger.info(f"[{account_name}] ❌ 平仓 {position.symbol} {position.get_side()} 使用monitor缓存盈亏: {actual_pnl:.2f} USDT")
                else:
                    actual_pnl = position.unrealized_pnl
                    close_price = position.mark_price
                    close_notional = abs(position.position_amt * position.mark_price) if position.position_amt != 0 else 0
                    logger.info(f"[{account_name}] ❌ 平仓 {position.symbol} {position.get_side()} 使用仓位盈亏: {actual_pnl:.2f} USDT")
            
            pnl_sign = "+" if actual_pnl >= 0 else ""
            logger.info(
                f"[{account_name}] ❌ 平仓 {position.symbol} {position.get_side()} 实际盈亏: {pnl_sign}{actual_pnl:.2f} USDT"
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
        
        def on_decrease(new_position, old_position, order_cache=None):
            decrease_amt = abs(old_position.position_amt) - abs(new_position.position_amt)
            old_notional = abs(old_position.notional)
            new_notional = abs(new_position.notional)
            decrease_value = old_notional - new_notional
            logger.info(
                f"[{account_name}] ➖ 减仓 {new_position.symbol} -{decrease_amt:.4f}币 "
                f"仓位: {old_notional:.2f} → {new_notional:.2f} USDT (-{decrease_value:.2f})"
            )
            position_data = _create_position_data(new_position, old_position)
            if order_cache:
                position_data['actual_pnl'] = order_cache.get('actual_pnl')
                position_data['close_price'] = order_cache.get('close_price')
            self.aggregator.add_position_change(position_data, 'REDUCE', old_position)
        
        monitor.on_position_opened = on_open
        monitor.on_position_closed = on_close
        monitor.on_position_increased = on_increase
        monitor.on_position_decreased = on_decrease
    
    def _init_positions(self):
        pass
    
    def _start_user_data_streams(self):
        """启动所有账户的用户数据流"""
        for account in self.accounts:
            try:
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
            except Exception as e:
                logger.error(f"❌ [{account['name']}] 账户启动失败: {e}", exc_info=True)
                self.telegram.send_message_sync(f"⚠️ <b>账户启动失败</b>\n\n账户: {account['name']}\n错误: {e}")
    
    def _start_keepalive_thread(self, account: Dict):
        """为指定账户启动listenKey保活线程"""
        def keepalive():
            client: BinanceClient = account['client']
            listen_endpoint: str = account['listen_endpoint']
            keepalive_interval = Settings().LISTEN_KEY_KEEPALIVE_INTERVAL
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
        pass
    
    def _start_event_loop(self):
        def run_loop():
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            logger.info("✅ 后台事件循环已启动")
            self.event_loop.run_forever()
        
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        time.sleep(0.1)
    
    def _stop_event_loop(self):
        if self.event_loop:
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)
            logger.info("⛔ 后台事件循环已停止")
    
    def start(self):
        """启动监控"""
        try:
            enabled_accounts = [acc['name'] for acc in self.accounts]
            logger.info(
                f"🚀 币安合约监控启动 (测试网: {Settings().BINANCE_TESTNET}) | 账户: {', '.join(enabled_accounts)}"
            )
            self.is_running = True
            
            self._start_event_loop()
            self.aggregator.event_loop = self.event_loop
            
            self._init_positions()
            self._start_user_data_streams()
            self._start_telegram_bot()
            
            account_text = "、".join(enabled_accounts)
            self.telegram.send_message_sync(
                "🚀 <b>币安合约监控 v2.1.0</b>\n"
                "━━━━━━━━━━━━━━\n\n"
                f"📊 <b>监听账户:</b> {account_text}\n"
                f"🔔 <b>推送内容:</b> 开仓/加仓/减仓/平仓通知\n\n"
                f"✨ <b>新功能:</b>\n"
                f"• 交易对可直接点击复制\n"
                f"• 显示具体Token名称（如VFY、BTC）\n"
                f"• 优化消息格式，统一字体粗细\n"
                f"• 修复初始仓位显示问题\n"
                f"• 精确显示每次减仓的盈亏\n\n"
                f"⏰ <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>"
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
        self._stop_event_loop()
        
        for account in self.accounts:
            ws: Optional[UserDataStreamWebSocket] = account.get('ws')
            if ws:
                ws.close()
            listen_key = account.get('listen_key')
            if listen_key:
                try:
                    result = account['client'].close_user_data_stream(listen_key, account['listen_endpoint'])
                    if result.get('msg') == 'listenKey already expired':
                        logger.debug(f"[{account['name']}] listenKey已过期，无需删除")
                    else:
                        logger.info(f"[{account['name']}] ✅ listenKey已成功删除")
                except Exception as e:
                    logger.warning(f"[{account['name']}] ⚠️ 关闭listenKey时出现异常: {e}")
        try:
            if self.restart_requested:
                self.telegram.send_message_sync("🔄 <b>币安合约监控正在重启...</b>")
            else:
                self.telegram.send_message_sync("⛔ <b>币安合约监控已停止</b>")
        except Exception as e:
            logger.error(f"发送停止通知失败: {e}")
        
        if self.restart_requested:
            # 检查是否由 supervisor 管理
            if 'SUPERVISOR_PROCESS_NAME' in os.environ:
                logger.info("🔄 监控已停止，等待 supervisor 重启...")
            else:
                logger.info("🔄 监控已停止，执行手动重启...")
                self._restart_application()
        else:
            logger.info("⛔ 监控已停止")
    
    def _restart_application(self):
        try:
            logger.info("🔄 正在重启应用程序...")
            python_executable = sys.executable
            script_path = os.path.abspath(__file__)
            os.execv(python_executable, [python_executable, script_path])
        except Exception as e:
            logger.error(f"重启失败: {e}")
            sys.exit(1)


def main():
    try:
        app = BinanceMonitorApp()
        app.start()
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)


if __name__ == "__main__":
    main()