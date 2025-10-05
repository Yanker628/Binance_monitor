"""币安WebSocket连接模块"""
import json
import time
import threading
from typing import Callable, Optional, Dict, Any, Set
from websocket import WebSocketApp
import logging

# 使用主程序的 logger
logger = logging.getLogger('binance_monitor')


class BinanceWebSocket:
    """币安WebSocket客户端"""
    
    def __init__(self, ws_url: str, auto_reconnect: bool = True, max_reconnect_attempts: int = 5):
        self.ws_url = ws_url
        self.ws: Optional[WebSocketApp] = None
        self.is_running = False
        self.should_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_attempts = 0
        self.callbacks: Dict[str, Callable] = {}
        self.ping_thread: Optional[threading.Thread] = None
        self.ws_thread: Optional[threading.Thread] = None
        
        # 已知但可忽略的事件类型（不需要处理，也不需要警告）
        self.ignored_events: Set[str] = {
            'TRADE_LITE',      # 交易简报（轻量级）
            'listenKeyExpired', # listenKey过期提醒
        }
        
        # 已警告过的未知事件类型（避免重复警告）
        self._warned_events: Set[str] = set()
        
        # 连接状态标志
        self._intentional_close = False  # 是否是主动关闭
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            # 处理 ping/pong
            if 'ping' in data:
                logger.debug("🏓 收到 ping，发送 pong")
                ws.send(json.dumps({'pong': data['ping']}))
                return
            
            event_type = data.get('e', '')
            
            # 处理已注册的事件
            if event_type in self.callbacks:
                logger.debug(f"📨 收到事件: {event_type}")
                self.callbacks[event_type](data)
            elif event_type in self.ignored_events:
                # 已知但忽略的事件类型，不打印任何日志
                pass
            elif event_type:
                # 未知事件类型，只警告一次
                if event_type not in self._warned_events:
                    logger.warning(
                        f"⚠️ 收到未注册的事件类型: {event_type}\n"
                        f"   已注册: {list(self.callbacks.keys())}\n"
                        f"   如果这是正常的，可以在 ignored_events 中忽略它"
                    )
                    self._warned_events.add(event_type)
            else:
                # 没有事件类型的消息
                logger.debug(f"📩 收到无事件类型的消息: {json.dumps(data, ensure_ascii=False)[:200]}")
                
        except Exception as e:
            logger.error(f"❌ WebSocket 消息处理错误: {e}", exc_info=True)
    
    def on_error(self, ws, error):
        logger.error(f"❌ WebSocket错误: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket关闭回调"""
        self.is_running = False
        
        # 如果是主动关闭，不尝试重连
        if self._intentional_close:
            logger.info(f"⛔ WebSocket已主动关闭")
            return
        
        # 如果启用了自动重连，尝试重连
        if self.should_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            wait_time = min(2 ** self.reconnect_attempts, 60)  # 指数退避，最多60秒
            logger.warning(
                f"⚠️ WebSocket连接断开 (状态码: {close_status_code}), "
                f"将在 {wait_time}秒后重连 (尝试 {self.reconnect_attempts}/{self.max_reconnect_attempts})"
            )
            time.sleep(wait_time)
            self._reconnect()
        else:
            logger.error(f"❌ WebSocket连接关闭，已达到最大重连次数或未启用自动重连")
    
    def on_open(self, ws):
        """WebSocket连接成功回调"""
        self.is_running = True
        self.reconnect_attempts = 0  # 重置重连计数
        logger.info("✅ WebSocket已连接")
    
    def _reconnect(self):
        """内部重连方法"""
        try:
            logger.info(f"🔄 正在尝试重新连接WebSocket...")
            self.connect()
        except Exception as e:
            logger.error(f"❌ WebSocket重连失败: {e}")
    
    def register_callback(self, event_type: str, callback: Callable):
        self.callbacks[event_type] = callback
    
    def connect(self):
        """连接WebSocket"""
        self._intentional_close = False
        
        self.ws = WebSocketApp(
            self.ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        self.ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
        self.ws_thread.start()
        
        timeout = 10
        start_time = time.time()
        while not self.is_running and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if not self.is_running:
            raise ConnectionError("WebSocket连接超时")
    
    def _run_websocket(self):
        """在线程中运行WebSocket"""
        try:
            if self.ws:
                self.ws.run_forever(
                    ping_interval=30,  # 每30秒发送ping
                    ping_timeout=10    # ping超时10秒
                )
        except Exception as e:
            if not self._intentional_close:
                logger.error(f"❌ WebSocket运行异常: {e}")
    
    def send(self, data: Dict[str, Any]):
        if self.ws and self.is_running:
            self.ws.send(json.dumps(data))
    
    def close(self):
        """主动关闭WebSocket连接"""
        self._intentional_close = True
        self.should_reconnect = False
        if self.ws:
            self.ws.close()
            self.is_running = False
            logger.info("⛔ WebSocket正在关闭...")


class UserDataStreamWebSocket(BinanceWebSocket):
    """用户数据流WebSocket"""
    
    def __init__(self, listen_key: str, ws_base_url: str):
        ws_url = f"{ws_base_url}/{listen_key}"
        logger.info(f"🔌 创建WebSocket连接: {ws_url}")
        super().__init__(ws_url)
        self.listen_key = listen_key
