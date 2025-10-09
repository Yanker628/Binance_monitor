"""
消息聚合器模块 - 解决多条消息推送聚合问题
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from decimal import Decimal

# 使用主程序的 logger
logger = logging.getLogger('binance_monitor')


class MessageAggregator:
    """
    消息聚合器
    
    功能：
    1. 将同一交易对在短时间窗口内的多次变动聚合为一条消息
    2. 防止重复推送
    3. 按时间窗口批量发送，减少Telegram消息数量
    """
    
    def __init__(self, send_callback: Callable, window_ms: int = 1000, event_loop: Optional[asyncio.AbstractEventLoop] = None):
        """
        初始化聚合器
        
        Args:
            send_callback: 发送消息的回调函数
            window_ms: 聚合窗口时间（毫秒），默认1000ms
            event_loop: 事件循环（可选，用于在非异步上下文中使用）
        """
        self.send_callback = send_callback
        self.window_ms = window_ms
        self.event_loop = event_loop
        
        # 仓位变动缓冲区: key = "symbol_positionSide", value = buffer_info
        self._position_buffers: Dict[str, Dict[str, Any]] = {}
        
        # 当前正在运行的聚合任务
        self._aggregate_task: Optional[asyncio.Task] = None
        
        # 上次发送的状态签名，用于防止重复推送
        self._last_sent_state: Dict[str, tuple] = {}
        
        # 状态签名清理计数器（每1000次操作清理一次）
        self._state_cleanup_counter = 0
        
        logger.info(f"消息聚合器已初始化，聚合窗口: {window_ms}ms")
    
    def add_position_change(self, position_data: Dict[str, Any], change_type: str, 
                          old_position: Optional[Any] = None):
        """
        添加仓位变动到聚合缓冲区
        
        Args:
            position_data: 仓位数据
            change_type: 变动类型 (OPEN/CLOSE/ADD/REDUCE)
            old_position: 旧仓位对象（用于获取平仓前数据）
        """
        symbol = position_data.get('symbol', 'UNKNOWN')
        logger.info(f"[聚合] 📥 接收到仓位变动: {symbol} {change_type}")
        
        try:
            # 优先使用提供的事件循环，否则尝试获取运行中的循环
            if self.event_loop:
                loop = self.event_loop
                logger.debug(f"[聚合] 使用提供的事件循环")
            else:
                loop = asyncio.get_running_loop()
                logger.debug(f"[聚合] 使用运行中的事件循环")
            
            loop.call_soon_threadsafe(
                self._update_position_buffer, 
                position_data, 
                change_type, 
                old_position
            )
            logger.debug(f"[聚合] 已调用 call_soon_threadsafe")
        except RuntimeError as e:
            # 如果没有运行中的事件循环，记录警告
            logger.error(f"❌ 没有运行中的事件循环，无法聚合消息: {e}")
        except Exception as e:
            logger.error(f"❌ 添加仓位变动时出错: {e}", exc_info=True)
    
    def _get_buffer_key(self, symbol: str, position_side: str) -> str:
        """生成缓冲区key"""
        return f"{symbol}_{position_side}"
    
    def _update_position_buffer(self, position_data: Dict[str, Any], 
                               change_type: str, old_position: Optional[Any]):
        """
        更新仓位缓冲区（在事件循环中调用）
        """
        symbol = position_data.get('symbol', '')
        position_side = position_data.get('position_side', 'BOTH')
        key = self._get_buffer_key(symbol, position_side)
        
        buffer = self._position_buffers.get(key)
        
        if not buffer:
            # 创建新的缓冲区
            buffer = {
                'key': key,
                'symbol': symbol,
                'position_side': position_side,
                'change_type': change_type,
                'first_prev_amount': position_data.get('previous_amount', 0),
                'first_prev_entry': position_data.get('old_entry_price', 0),
                'first_prev_unrealized_pnl': position_data.get('old_unrealized_pnl', 0),
                'current_data': position_data,
                'old_position': old_position,
                'update_count': 1,
                'last_update_time': datetime.now()
            }
            self._position_buffers[key] = buffer
            logger.info(f"[聚合] 创建新缓冲区: {key}, 类型: {change_type}")
        else:
            # 更新现有缓冲区
            buffer['current_data'] = position_data
            buffer['change_type'] = change_type
            buffer['update_count'] += 1
            buffer['last_update_time'] = datetime.now()
            if old_position:
                buffer['old_position'] = old_position
            logger.info(f"[聚合] 更新缓冲区: {key}, 类型: {change_type}, 次数: {buffer['update_count']}")
        
        # 如果没有运行中的聚合任务，创建新的
        if self._aggregate_task is None or self._aggregate_task.done():
            loop = asyncio.get_running_loop()
            self._aggregate_task = loop.create_task(self._flush_messages())
            
            def task_done_callback(task):
                try:
                    exc = task.exception()
                    if exc:
                        logger.error(f"[聚合] 聚合任务异常: {exc}", exc_info=True)
                except asyncio.CancelledError:
                    logger.info(f"[聚合] 聚合任务被取消")
            
            self._aggregate_task.add_done_callback(task_done_callback)
            logger.info(f"[聚合] 启动聚合任务，窗口时长: {self.window_ms}ms")
    
    async def _flush_messages(self):
        """刷新缓冲区，发送聚合后的消息"""
        try:
            # 等待聚合窗口
            logger.info(f"[聚合] 等待聚合窗口: {self.window_ms}ms")
            await asyncio.sleep(self.window_ms / 1000)
            logger.info(f"[聚合] 聚合窗口结束，开始处理缓冲")
            
            if not self._position_buffers:
                logger.info(f"[聚合] 缓冲区为空，无需推送")
                self._aggregate_task = None
                return
            
            # 原子操作：取出所有buffer并清空
            buffers = list(self._position_buffers.values())
            logger.info(f"[聚合] 从缓冲区取出 {len(buffers)} 个仓位变动")
            self._position_buffers.clear()
            self._aggregate_task = None
            
            # 构建聚合消息
            messages: List[str] = []
            for buffer in buffers:
                aggregated = self._build_aggregated_message(buffer)
                if not aggregated:
                    logger.info(f"[聚合] 构建消息失败，跳过: {buffer.get('key')}")
                    continue
                
                # 检查是否重复
                key = buffer.get('key')
                if key:
                    signature = self._get_message_signature(buffer)
                    if self._last_sent_state.get(key) == signature:
                        logger.info(f"[聚合] 检测到重复消息，跳过: {key}")
                        continue
                    self._last_sent_state[key] = signature
                    
                    # 定期清理状态签名字典，防止内存泄漏
                    self._state_cleanup_counter += 1
                    if self._state_cleanup_counter >= 1000:  # 每1000次操作清理一次
                        self._cleanup_state_signatures()
                        self._state_cleanup_counter = 0
                
                messages.append(aggregated)
            
            if not messages:
                logger.info(f"[聚合] 聚合窗口结束但无有效变化，跳过推送")
                return
            
            # 发送聚合后的消息
            combined_message = "\n\n".join(messages)
            logger.info(f"[聚合] 准备推送聚合消息，包含 {len(messages)} 条仓位变动")
            
            # 调用发送回调
            try:
                logger.info(f"[聚合] 🔔 开始调用 Telegram 发送回调...")
                if asyncio.iscoroutinefunction(self.send_callback):
                    await self.send_callback(combined_message)
                else:
                    # 同步回调在线程池中执行，避免阻塞事件循环
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.send_callback, combined_message)
                logger.info(f"[聚合] ✅ Telegram 推送完成")
            except Exception as send_error:
                logger.error(f"[聚合] ❌ Telegram 发送失败: {send_error}", exc_info=True)
            
        except Exception as e:
            logger.error(f"[聚合] 刷新消息时出错: {e}", exc_info=True)
    
    def _get_message_signature(self, buffer: Dict[str, Any]) -> tuple:
        """生成消息签名，用于去重"""
        data = buffer['current_data']
        return (
            buffer['change_type'],
            str(buffer.get('first_prev_amount', 0)),
            str(data.get('position_amt', 0)),
            str(data.get('entry_price', 0)),
            str(buffer.get('first_prev_entry', 0)),
        )
    
    def _cleanup_state_signatures(self):
        """清理状态签名字典，防止内存泄漏"""
        try:
            # 保留最近100个状态签名，清理旧的
            if len(self._last_sent_state) > 100:
                # 转换为列表，按添加顺序排序（Python 3.7+ 字典保持插入顺序）
                items = list(self._last_sent_state.items())
                # 保留最后100个
                recent_items = items[-100:]
                self._last_sent_state = dict(recent_items)
                logger.info(f"[聚合] 清理状态签名，保留最近100个，清理前: {len(items)}, 清理后: {len(self._last_sent_state)}")
        except Exception as e:
            logger.error(f"[聚合] 清理状态签名时出错: {e}")
    
    def _build_aggregated_message(self, buffer: Dict[str, Any]) -> Optional[str]:
        """
        构建聚合后的消息
        
        根据缓冲区中的数据，计算整体变化并生成消息文本
        """
        try:
            data = buffer['current_data']
            change_type = buffer['change_type']
            symbol = buffer['symbol']
            update_count = buffer['update_count']
            
            # 获取首次和当前的仓位数据
            first_prev_amount = Decimal(str(buffer.get('first_prev_amount', 0)))
            first_prev_entry = Decimal(str(buffer.get('first_prev_entry', 0)))
            first_prev_pnl = Decimal(str(buffer.get('first_prev_unrealized_pnl', 0)))
            
            current_amount = Decimal(str(data.get('position_amt', 0)))
            current_entry = Decimal(str(data.get('entry_price', 0)))
            current_pnl = Decimal(str(data.get('unrealized_pnl', 0)))
            
            # 对于平仓事件，使用old_position中的实际仓位数据
            old_position = buffer.get('old_position')
            if old_position and change_type == 'CLOSE':
                # 使用old_position中的实际仓位数据
                first_prev_amount = Decimal(str(old_position.position_amt))
                first_prev_entry = Decimal(str(old_position.entry_price))
                first_prev_pnl = Decimal(str(old_position.unrealized_pnl))
                logger.info(f"[聚合] 平仓事件使用old_position数据: 仓位={first_prev_amount}, 均价={first_prev_entry}")
            elif change_type == 'CLOSE' and update_count > 1:
                # 如果有多次更新且是平仓事件，使用current_data中的previous_amount
                # 这确保我们使用最后一次减仓后的数据
                first_prev_amount = Decimal(str(data.get('previous_amount', 0)))
                logger.info(f"[聚合] 平仓事件使用previous_amount数据: 仓位={first_prev_amount}")
            
            # 计算实际变化
            prev_amt_abs = abs(first_prev_amount)
            curr_amt_abs = abs(current_amount)
            
            # 如果前后数量相同，跳过（但平仓事件除外）
            if prev_amt_abs == curr_amt_abs and change_type != 'CLOSE':
                logger.info(f"[聚合] 仓位数量未变化，跳过: {symbol}")
                return None
            
            # 重新判断变化类型（基于首次和当前的对比）
            if prev_amt_abs == 0 and curr_amt_abs > 0:
                actual_change_type = 'OPEN'
            elif prev_amt_abs > 0 and curr_amt_abs == 0:
                actual_change_type = 'CLOSE'
            elif curr_amt_abs > prev_amt_abs:
                actual_change_type = 'ADD'
            elif curr_amt_abs < prev_amt_abs:
                actual_change_type = 'REDUCE'
            else:
                actual_change_type = change_type
            
            # 计算变化百分比
            if prev_amt_abs > 0:
                delta_pct = abs((curr_amt_abs - prev_amt_abs) / prev_amt_abs * 100)
            else:
                delta_pct = Decimal('100.0')
            
            # 构建聚合后的数据字典
            aggregated_data = {
                'symbol': symbol,
                'position_side': data.get('position_side', 'BOTH'),
                'change_type': actual_change_type,
                'position_amt': current_amount,
                'previous_amount': first_prev_amount,
                'entry_price': current_entry if curr_amt_abs > 0 else first_prev_entry,
                'old_entry_price': first_prev_entry,
                'unrealized_pnl': current_pnl if curr_amt_abs > 0 else first_prev_pnl,
                'leverage': data.get('leverage', 1),
                'notional': data.get('notional', 0),
                'delta_pct': float(delta_pct),
                'update_count': update_count,
                'update_time': buffer.get('last_update_time', datetime.now())
            }
            
            # 如果是平仓，使用实际盈亏数据
            if actual_change_type == 'CLOSE':
                old_position = buffer.get('old_position')
                previous_side = data.get('previous_side', 'NONE')
                aggregated_data['previous_side'] = previous_side
                
                actual_pnl = data.get('actual_pnl')
                close_price = data.get('close_price', current_entry)
                close_notional = data.get('close_notional', 0)
                
                if actual_pnl is not None:
                    aggregated_data['unrealized_pnl'] = actual_pnl
                    aggregated_data['notional'] = close_notional
                    aggregated_data['entry_price'] = close_price
                    logger.info(f"[聚合] 使用订单更新事件的实际盈亏: {actual_pnl:.2f} USDT, 平仓前仓位: {close_notional:.2f} USDT")
                else:
                    entry_price = data.get('old_entry_price', first_prev_entry)
                    previous_amount = data.get('previous_amount', first_prev_amount)
                    
                    if old_position:
                        entry_price = old_position.entry_price
                        previous_amount = old_position.position_amt
                        close_price = data.get('close_price', old_position.mark_price)
                    
                    cumulative_pnl = previous_amount * (close_price - entry_price)
                    aggregated_data['unrealized_pnl'] = cumulative_pnl
                    aggregated_data['notional'] = abs(previous_amount * close_price)
                    aggregated_data['entry_price'] = close_price
                    logger.info(f"[聚合] 使用计算方式的实际盈亏: {cumulative_pnl:.2f} USDT")
                
                aggregated_data['close_price'] = close_price
                aggregated_data['original_entry_price'] = data.get('old_entry_price', first_prev_entry)
            
            # 导入formatter生成消息文本
            from utils.formatter import (
                format_open_position_message,
                format_close_position_message,
                format_increase_position_message,
                format_decrease_position_message
            )
            
            # 创建临时Position对象用于格式化
            class TempPosition:
                def __init__(self, data):
                    self.symbol = data['symbol']
                    self.position_side = data['position_side']
                    self.position_amt = float(data['position_amt'])
                    self.entry_price = float(data['entry_price'])
                    self.unrealized_pnl = float(data['unrealized_pnl'])
                    self.leverage = data['leverage']
                    self.notional = float(data['notional'])
                    self.update_time = data['update_time']
                    # 保存平仓前的方向（用于平仓时显示正确的方向）
                    self.previous_side = data.get('previous_side', None)
                
                def get_side(self):
                    # 如果有保存的previous_side（平仓情况），使用它
                    if self.previous_side:
                        return self.previous_side
                    # 否则根据position_amt判断
                    if self.position_amt > 0:
                        return 'LONG'
                    elif self.position_amt < 0:
                        return 'SHORT'
                    else:
                        return 'NONE'
            
            position = TempPosition(aggregated_data)
            
            # 根据变化类型生成消息
            if actual_change_type == 'OPEN':
                message = format_open_position_message(position)
            elif actual_change_type == 'CLOSE':
                old_pos = buffer.get('old_position')
                message = format_close_position_message(position, old_pos)
            elif actual_change_type == 'ADD':
                old_pos = TempPosition({
                    **aggregated_data,
                    'position_amt': float(first_prev_amount),
                    'entry_price': float(first_prev_entry)
                })
                message = format_increase_position_message(position, old_pos)
            elif actual_change_type == 'REDUCE':
                old_pos = TempPosition({
                    **aggregated_data,
                    'position_amt': float(first_prev_amount),
                    'entry_price': float(first_prev_entry)
                })
                message = format_decrease_position_message(position, old_pos)
            else:
                return None
            
            # 如果有多次更新，只在日志中记录
            if update_count > 1:
                logger.info(f"[聚合] {symbol} 聚合了 {update_count} 次变动")
            
            return message
            
        except Exception as e:
            logger.error(f"[聚合] 构建消息失败: {e}", exc_info=True)
            return None

