"""币安WebSocket连接模块"""
import json
import time
import threading
import ssl
import logging
from typing import Callable, Optional, Dict, Any, Set
from websocket import WebSocketApp
import certifi

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
        
        self.ssl_context = self._create_secure_ssl_context()
        
        self._last_connect_time = 0
        self._min_connect_interval = 5
        
        self._message_times = []
        self._max_messages_per_minute = 1000
        
        self.ignored_events: Set[str] = {
            'TRADE_LITE',
            'listenKeyExpired',
        }
        
        self._warned_events: Set[str] = set()
        self._intentional_close = False
        
        logger.info(f"🔒 WebSocket客户端已初始化，SSL验证已启用")
    
    def _create_secure_ssl_context(self) -> ssl.SSLContext:
        try:
            context = ssl.create_default_context()
            
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            
            context.load_verify_locations(certifi.where())
            
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.maximum_version = ssl.TLSVersion.TLSv1_3
            
            context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
            
            logger.info("✅ SSL上下文创建成功，已启用证书验证")
            return context
            
        except Exception as e:
            logger.error(f"❌ SSL上下文创建失败: {e}")
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            return context
    
    def _validate_websocket_url(self, url: str) -> bool:
        if not url:
            logger.error("❌ WebSocket URL为空")
            return False
        
        if not url.startswith(('wss://', 'ws://')):
            logger.error(f"❌ 无效的WebSocket协议: {url}")
            return False
        
        if url.startswith('ws://') and 'testnet' not in url:
            logger.warning(f"⚠️ 生产环境建议使用WSS协议: {url}")
        
        if 'binance' not in url.lower():
            logger.warning(f"⚠️ 非币安官方域名: {url}")
        
        logger.info(f"✅ WebSocket URL验证通过: {url}")
        return True
        
    def _check_message_frequency(self) -> bool:
        now = time.time()
        
        self._message_times = [t for t in self._message_times if now - t < 60]
        
        if len(self._message_times) >= self._max_messages_per_minute:
            logger.warning(f"⚠️ WebSocket消息频率过高: {len(self._message_times)}/{self._max_messages_per_minute} 每分钟")
            return False
        
        self._message_times.append(now)
        return True
    
    def _validate_message_size(self, message: str) -> bool:
        max_size = 1024 * 1024
        if len(message) > max_size:
            logger.warning(f"⚠️ WebSocket消息过大: {len(message)} 字节，限制: {max_size} 字节")
            return False
        return True
    
    def on_message(self, ws, message):
        try:
            # 检查消息频率
            if not self._check_message_frequency():
                logger.warning("⚠️ 消息频率过高，跳过处理")
                return
            
            # 验证消息大小
            if not self._validate_message_size(message):
                logger.warning("⚠️ 消息过大，跳过处理")
                return
            
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
        """安全连接WebSocket"""
        self._intentional_close = False
        
        # 检查连接频率
        now = time.time()
        if now - self._last_connect_time < self._min_connect_interval:
            wait_time = self._min_connect_interval - (now - self._last_connect_time)
            logger.warning(f"⚠️ 连接过于频繁，等待 {wait_time:.1f} 秒后重试")
            time.sleep(wait_time)
        
        self._last_connect_time = time.time()
        
        # 验证URL安全性
        if not self._validate_websocket_url(self.ws_url):
            raise ConnectionError(f"WebSocket URL验证失败: {self.ws_url}")
        
        try:
            self.ws = WebSocketApp(
                self.ws_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            logger.info(f"🔒 正在建立安全WebSocket连接: {self.ws_url}")
            
            self.ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
            self.ws_thread.start()
            
            timeout = 15  # 增加超时时间
            start_time = time.time()
            while not self.is_running and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.is_running:
                raise ConnectionError("WebSocket连接超时")
                
        except ssl.SSLError as e:
            logger.error(f"❌ SSL连接错误: {e}")
            raise ConnectionError(f"SSL连接失败: {e}")
        except Exception as e:
            logger.error(f"❌ WebSocket连接失败: {e}")
            raise ConnectionError(f"WebSocket连接失败: {e}")
    
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
        """安全发送数据"""
        if not self.ws or not self.is_running:
            logger.warning("⚠️ WebSocket未连接，无法发送数据")
            return False
        
        try:
            # 验证数据大小
            message = json.dumps(data)
            if not self._validate_message_size(message):
                logger.warning("⚠️ 发送数据过大，已拒绝")
                return False
            
            # 检查发送频率
            if not self._check_message_frequency():
                logger.warning("⚠️ 发送频率过高，已拒绝")
                return False
            
            self.ws.send(message)
            logger.debug(f"📤 WebSocket数据发送成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket发送失败: {e}")
            return False
    
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
