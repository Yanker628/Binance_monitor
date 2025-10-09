"""
消息聚合器模块 - 解决多条消息推送聚合问题
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from decimal import Decimal

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
        self.send_callback = send_callback
        self.window_ms = window_ms
        self.event_loop = event_loop
        
        self._position_buffers: Dict[str, Dict[str, Any]] = {}
        self._aggregate_task: Optional[asyncio.Task] = None
        self._last_sent_state: Dict[str, tuple] = {}
        self._state_cleanup_counter = 0
        
        logger.info(f"消息聚合器已初始化，聚合窗口: {window_ms}ms")
    
    def add_position_change(self, position_data: Dict[str, Any], change_type: str, 
                          old_position: Optional[Any] = None):
        symbol = position_data.get('symbol', 'UNKNOWN')
        logger.info(f"[聚合] 📥 接收到仓位变动: {symbol} {change_type}")
        
        try:
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
            logger.error(f"❌ 没有运行中的事件循环，无法聚合消息: {e}")
        except Exception as e:
            logger.error(f"❌ 添加仓位变动时出错: {e}", exc_info=True)
    
    def _get_buffer_key(self, symbol: str, position_side: str) -> str:
        return f"{symbol}_{position_side}"
    
    def _update_position_buffer(self, position_data: Dict[str, Any], 
                               change_type: str, old_position: Optional[Any]):
        symbol = position_data.get('symbol', '')
        position_side = position_data.get('position_side', 'BOTH')
        key = self._get_buffer_key(symbol, position_side)
        
        buffer = self._position_buffers.get(key)
        
        if not buffer:
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
                'last_update_time': datetime.now(),
                # 记录初始仓位信息，用于平仓时计算总仓位
                'initial_amount': position_data.get('previous_amount', 0),
                'initial_entry': position_data.get('old_entry_price', 0),
                'initial_pnl': position_data.get('old_unrealized_pnl', 0)
            }
            self._position_buffers[key] = buffer
            logger.info(f"[聚合] 创建新缓冲区: {key}, 类型: {change_type}")
        else:
            buffer['current_data'] = position_data
            buffer['change_type'] = change_type
            buffer['update_count'] += 1
            buffer['last_update_time'] = datetime.now()
            if old_position:
                buffer['old_position'] = old_position
            logger.info(f"[聚合] 更新缓冲区: {key}, 类型: {change_type}, 次数: {buffer['update_count']}")
        
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
        try:
            logger.info(f"[聚合] 等待聚合窗口: {self.window_ms}ms")
            await asyncio.sleep(self.window_ms / 1000)
            logger.info(f"[聚合] 聚合窗口结束，开始处理缓冲")
            
            if not self._position_buffers:
                logger.info(f"[聚合] 缓冲区为空，无需推送")
                self._aggregate_task = None
                return
            
            buffers = list(self._position_buffers.values())
            logger.info(f"[聚合] 从缓冲区取出 {len(buffers)} 个仓位变动")
            self._position_buffers.clear()
            self._aggregate_task = None
            
            messages: List[str] = []
            for buffer in buffers:
                aggregated = self._build_aggregated_message(buffer)
                if not aggregated:
                    logger.info(f"[聚合] 构建消息失败，跳过: {buffer.get('key')}")
                    continue
                
                key = buffer.get('key')
                if key:
                    signature = self._get_message_signature(buffer)
                    if self._last_sent_state.get(key) == signature:
                        logger.info(f"[聚合] 检测到重复消息，跳过: {key}")
                        continue
                    self._last_sent_state[key] = signature
                    
                    self._state_cleanup_counter += 1
                    if self._state_cleanup_counter >= 1000:
                        self._cleanup_state_signatures()
                        self._state_cleanup_counter = 0
                
                messages.append(aggregated)
            
            if not messages:
                logger.info(f"[聚合] 聚合窗口结束但无有效变化，跳过推送")
                return
            
            combined_message = "\n\n".join(messages)
            logger.info(f"[聚合] 准备推送聚合消息，包含 {len(messages)} 条仓位变动")
            
            try:
                logger.info(f"[聚合] 🔔 开始调用 Telegram 发送回调...")
                if asyncio.iscoroutinefunction(self.send_callback):
                    await self.send_callback(combined_message)
                else:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.send_callback, combined_message)
                logger.info(f"[聚合] ✅ Telegram 推送完成")
            except Exception as send_error:
                logger.error(f"[聚合] ❌ Telegram 发送失败: {send_error}", exc_info=True)
            
        except Exception as e:
            logger.error(f"[聚合] 刷新消息时出错: {e}", exc_info=True)
    
    def _get_message_signature(self, buffer: Dict[str, Any]) -> tuple:
        data = buffer['current_data']
        return (
            buffer['change_type'],
            str(buffer.get('first_prev_amount', 0)),
            str(data.get('position_amt', 0)),
            str(data.get('entry_price', 0)),
            str(buffer.get('first_prev_entry', 0)),
        )
    
    def _cleanup_state_signatures(self):
        try:
            if len(self._last_sent_state) > 100:
                items = list(self._last_sent_state.items())
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
                # 只有在真正完全平仓时才标记为CLOSE
                # 检查是否是从有仓位变为完全空仓
                if change_type == 'CLOSE' or (first_prev_amount != 0 and current_amount == 0):
                    actual_change_type = 'CLOSE'
                else:
                    actual_change_type = 'REDUCE'
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
            
            # 对于平仓事件，需要计算总仓位和总盈亏
            if actual_change_type == 'CLOSE':
                # 获取聚合期间的初始仓位信息
                total_original_amount = Decimal(str(buffer.get('initial_amount', buffer.get('first_prev_amount', 0))))
                total_original_entry = Decimal(str(buffer.get('initial_entry', buffer.get('first_prev_entry', 0))))
                total_original_pnl = Decimal(str(buffer.get('initial_pnl', buffer.get('first_prev_unrealized_pnl', 0))))
                
                # 计算总盈亏 - 使用订单更新事件的实际盈亏（如果可用）
                actual_pnl = data.get('actual_pnl')
                if actual_pnl is not None:
                    # 使用订单事件提供的实际盈亏（这是整个交易周期的总盈亏）
                    total_pnl = Decimal(str(actual_pnl))
                    logger.info(f"[聚合] 平仓使用订单实际盈亏: {total_pnl:.2f} USDT (总盈亏)")
                else:
                    # 如果没有订单实际盈亏，计算总盈亏
                    close_price = data.get('close_price', current_entry)
                    total_pnl = total_original_amount * (Decimal(str(close_price)) - total_original_entry)
                    logger.info(f"[聚合] 平仓计算总盈亏: {total_pnl:.2f} USDT (数量:{total_original_amount}, 开仓:{total_original_entry}, 平仓:{close_price})")
                
                # 更新聚合数据，使用总仓位信息
                aggregated_data['position_amt'] = total_original_amount
                aggregated_data['previous_amount'] = total_original_amount
                aggregated_data['entry_price'] = total_original_entry
                aggregated_data['old_entry_price'] = total_original_entry
                aggregated_data['unrealized_pnl'] = total_pnl
                aggregated_data['notional'] = abs(total_original_amount * total_original_entry)
                aggregated_data['close_price'] = data.get('close_price', current_entry)
                aggregated_data['total_original_amount'] = total_original_amount
                aggregated_data['total_original_entry'] = total_original_entry
                aggregated_data['total_pnl'] = total_pnl
                
                logger.info(f"[聚合] 平仓总仓位: {total_original_amount} 币, 总盈亏: {total_pnl:.2f} USDT")
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

