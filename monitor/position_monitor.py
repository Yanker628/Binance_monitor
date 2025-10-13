"""仓位监控模块"""
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime
from utils.data_validator import PositionDataValidator, SafeDataProcessor

logger = logging.getLogger('binance_monitor')


class Position:
    """仓位数据类"""
    
    def __init__(self, data: Dict):
        processor = SafeDataProcessor()
        
        self.symbol = processor.safe_string_conversion(data.get('symbol', ''), 'UNKNOWN', '交易对')
        self.position_side = processor.safe_string_conversion(data.get('positionSide', 'BOTH'), 'BOTH', '仓位方向')
        self.position_amt = processor.safe_float_conversion(data.get('positionAmt', 0), 0, '仓位数量')
        self.entry_price = processor.safe_float_conversion(data.get('entryPrice', 0), 0, '开仓价格')
        self.mark_price = processor.safe_float_conversion(data.get('markPrice', 0), 0, '标记价格')
        self.unrealized_pnl = processor.safe_float_conversion(data.get('unRealizedProfit', 0), 0, '浮动盈亏')
        self.leverage = processor.safe_int_conversion(data.get('leverage', 1), 1, '杠杆')
        self.notional = processor.safe_float_conversion(data.get('notional', 0), 0, '名义价值')
        self.isolated = bool(data.get('isolated', False))
        self.update_time = datetime.now()
        self.initial_position: Optional['Position'] = None
    
    def is_empty(self) -> bool:
        return abs(self.position_amt) < 0.0001
    
    def get_side(self) -> str:
        if self.position_amt > 0:
            return 'LONG'
        elif self.position_amt < 0:
            return 'SHORT'
        else:
            return 'NONE'
    
    def get_pnl_percent(self) -> float:
        if self.entry_price > 0:
            return (self.unrealized_pnl / abs(self.notional)) * 100 if self.notional != 0 else 0
        return 0
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'side': self.get_side(),
            'position_side': self.position_side,
            'amount': self.position_amt,
            'entry_price': self.entry_price,
            'mark_price': self.mark_price,
            'unrealized_pnl': self.unrealized_pnl,
            'pnl_percent': self.get_pnl_percent(),
            'leverage': self.leverage,
            'notional': self.notional,
            'update_time': self.update_time.isoformat()
        }


class PositionMonitor:
    """仓位监控器"""
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.leverage_cache: Dict[str, int] = {}
        self.initial_positions: Dict[str, Position] = {}  # 保存初始仓位信息
        self.on_position_opened: Optional[Callable] = None
        self.on_position_closed: Optional[Callable] = None
        self.on_position_increased: Optional[Callable] = None
        self.on_position_decreased: Optional[Callable] = None
    
    def _get_position_key(self, symbol: str, position_side: str = 'BOTH') -> str:
        return f"{symbol}_{position_side}"
    
    def _create_position_dict(self, position: Position) -> Dict:
        return {
            'symbol': position.symbol,
            'position_side': position.position_side,
            'position_amt': position.position_amt,
            'entry_price': position.entry_price,
            'mark_price': position.mark_price,
            'unrealized_pnl': position.unrealized_pnl,
            'leverage': position.leverage,
            'notional': position.notional,
            'isolated': position.isolated
        }
    
    def update_positions(self, positions_data: List[Dict]):
        for pos_data in positions_data:
            position = Position(pos_data)
            key = self._get_position_key(position.symbol, position.position_side)
            
            if not position.is_empty():
                old_position = self.positions.get(key)
                
                if old_position is None or old_position.is_empty():
                    self.positions[key] = position
                    if self.on_position_opened:
                        self.on_position_opened(position)
                else:
                    old_amt = abs(old_position.position_amt)
                    new_amt = abs(position.position_amt)
                    
                    if new_amt > old_amt and self.on_position_increased:
                        self.on_position_increased(position, old_position)
                    elif new_amt < old_amt and self.on_position_decreased:
                        self.on_position_decreased(position, old_position)
                    
                    self.positions[key] = position
            else:
                old_position = self.positions.get(key)
                if old_position and not old_position.is_empty():
                    if self.on_position_closed:
                        self.on_position_closed(old_position)
                    self.positions[key] = position
    
    def handle_account_update(self, event_data: Dict):
        try:
            logger.info(f"🔄 处理账户更新事件")
            if event_data.get('e') != 'ACCOUNT_UPDATE':
                logger.warning(f"⚠️ 事件类型不是 ACCOUNT_UPDATE: {event_data.get('e')}")
                return
            
            positions_data = event_data.get('a', {}).get('P', [])
            logger.info(f"📊 收到 {len(positions_data)} 个仓位更新")
            
            processor = SafeDataProcessor()
            
            for pos_data in positions_data:
                try:
                    symbol = processor.safe_string_conversion(pos_data.get('s', ''), 'UNKNOWN', '交易对')
                    position_side = processor.safe_string_conversion(pos_data.get('ps', 'BOTH'), 'BOTH', '仓位方向')
                    position_amt = processor.safe_float_conversion(pos_data.get('pa', 0), 0, '仓位数量')
                    entry_price = processor.safe_float_conversion(pos_data.get('ep', 0), 0, '开仓价格')
                    unrealized_pnl = processor.safe_float_conversion(pos_data.get('up', 0), 0, '浮动盈亏')
                    leverage = processor.safe_int_conversion(pos_data.get('l', 1), 1, '杠杆')
                    
                    logger.debug(f"📦 原始数据 {symbol}: pa={position_amt}, ep={entry_price}, up={unrealized_pnl}, l={leverage}")
                    
                    key = self._get_position_key(symbol, position_side)
                    old_position = self.positions.get(key)
                    
                    mark_price = 0
                    notional = 0
                    if abs(position_amt) > 0.0001 and entry_price > 0:
                        # 正确的mark_price计算：mark_price = entry_price + (unrealized_pnl / position_amt)
                        mark_price = entry_price + (unrealized_pnl / position_amt)
                        notional = abs(position_amt * mark_price)
                    elif old_position and not old_position.is_empty():
                        mark_price = old_position.mark_price
                        notional = old_position.notional
                    
                    position_data = {
                        'symbol': symbol,
                        'positionSide': position_side,
                        'positionAmt': position_amt,
                        'entryPrice': entry_price,
                        'unRealizedProfit': unrealized_pnl,
                        'markPrice': mark_price,
                        'notional': notional,
                        'leverage': leverage
                    }
                    
                    validated_data = PositionDataValidator.validate_position_data(position_data)
                    position = Position(validated_data)
                    
                    if abs(position_amt) > 0.0001:
                        if old_position is None or old_position.is_empty():
                            self.positions[key] = position
                            # 保存初始仓位信息
                            self.initial_positions[key] = position
                            logger.info(f"💰 [{symbol}] 保存初始仓位: {position_amt:.4f}币 @ {entry_price:.4f}")
                            if self.on_position_opened:
                                self.on_position_opened(position)
                        else:
                            old_amt = abs(old_position.position_amt)
                            new_amt = abs(position_amt)
                            
                            if new_amt > old_amt and self.on_position_increased:
                                self.on_position_increased(position, old_position)
                            elif new_amt < old_amt and self.on_position_decreased:
                                # 减仓时不立即触发回调，等待订单更新事件
                                # 订单更新事件会包含实际盈亏信息，在那里触发回调
                                logger.info(f"💰 [{symbol}] 减仓事件，等待订单更新事件处理")
                                # 不调用 self.on_position_decreased，避免重复推送
                            
                            self.positions[key] = position
                    else:
                        if old_position and not old_position.is_empty():
                            order_cache = None
                            if hasattr(self, 'order_pnl_cache') and key in self.order_pnl_cache:
                                order_cache = self.order_pnl_cache.pop(key)
                                logger.info(f"💰 [{symbol}] 平仓时使用订单盈亏缓存: {order_cache['actual_pnl']:.4f} USDT")
                            
                            # 平仓时使用最后一次的old_position，但保存初始仓位信息供格式化使用
                            initial_position = self.initial_positions.get(key)
                            if initial_position:
                                logger.info(f"💰 [{symbol}] 平仓时保存初始仓位信息: {initial_position.position_amt:.4f}币 @ {initial_position.entry_price:.4f}")
                                # 将初始仓位信息附加到old_position上，供格式化函数使用
                                old_position.initial_position = initial_position
                            
                            if self.on_position_closed:
                                self.on_position_closed(old_position, order_cache)
                            
                            # 清理初始仓位缓存
                            if key in self.initial_positions:
                                del self.initial_positions[key]
                            
                            # 平仓时不触发减仓回调，避免重复推送
                            logger.info(f"💰 [{symbol}] 平仓事件已处理，跳过减仓回调")
                        
                        self.positions[key] = position
                        
                except ValueError as e:
                    logger.error(f"❌ 仓位数据验证失败: {e}")
                    continue
                except Exception as e:
                    logger.error(f"❌ 处理单个仓位数据时出错: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"处理账户更新失败: {e}", exc_info=True)
    
    def handle_order_update(self, event_data: Dict):
        try:
            logger.info(f"🔄 处理订单更新事件")
            if event_data.get('e') != 'ORDER_TRADE_UPDATE':
                logger.warning(f"⚠️ 事件类型不是 ORDER_TRADE_UPDATE: {event_data.get('e')}")
                return
            
            order_data = event_data.get('o', {})
            
            try:
                validated_order = PositionDataValidator.validate_order_data(order_data)
                
                symbol = validated_order['s']
                order_status = validated_order['X']
                executed_qty = validated_order['z']
                realized_pnl = validated_order['rp']
                position_side = validated_order['ps']
                close_price = validated_order['ap']
                
                logger.debug(f"📦 订单数据 {symbol}: 状态={order_status}, 数量={executed_qty}, 实际盈亏={realized_pnl}")
                
                # 当有实际盈亏时，说明是平仓或部分平仓
                if order_status in ['FILLED', 'PARTIALLY_FILLED'] and realized_pnl != 0 and executed_qty > 0:
                    key = self._get_position_key(symbol, position_side)
                    
                    logger.info(f"💰 [{symbol}] 订单成交: 数量={executed_qty} @ {close_price}, 实际盈亏: {realized_pnl:.4f} USDT")
                    
                    if not hasattr(self, 'order_pnl_cache'):
                        self.order_pnl_cache = {}
                    
                    # 聚合部分平仓的盈亏
                    if key in self.order_pnl_cache:
                        existing = self.order_pnl_cache[key]
                        total_quantity = existing['total_quantity'] + executed_qty
                        total_cost = existing['total_cost'] + (executed_qty * close_price)
                        total_pnl = existing['actual_pnl'] + realized_pnl
                        avg_close_price = total_cost / total_quantity if total_quantity > 0 else 0
                        
                        logger.info(f"💰 [{symbol}] 累计订单盈亏: {total_pnl:.4f} USDT (本次: {realized_pnl:.4f})")
                        
                        self.order_pnl_cache[key] = {
                            'actual_pnl': total_pnl,
                            'close_price': avg_close_price,
                            'quantity': executed_qty,
                            'total_quantity': total_quantity,
                            'total_cost': total_cost,
                            'last_pnl': realized_pnl,  # 记录本次盈亏
                        }
                    else:
                        logger.info(f"💰 [{symbol}] 首次订单盈亏: {realized_pnl:.4f} USDT")
                        self.order_pnl_cache[key] = {
                            'actual_pnl': realized_pnl,
                            'close_price': close_price,
                            'quantity': executed_qty,
                            'total_quantity': executed_qty,
                            'total_cost': executed_qty * close_price,
                            'last_pnl': realized_pnl,  # 记录本次盈亏
                        }
                    
                    # 订单更新后，如果有减仓回调，触发减仓推送
                    if self.on_position_decreased:
                        current_position = self.positions.get(key)
                        if current_position and not current_position.is_empty():
                            # 创建本次减仓的缓存
                            order_cache = {
                                'actual_pnl': realized_pnl,
                                'close_price': close_price
                            }
                            logger.info(f"💰 [{symbol}] 订单更新后触发减仓推送: {realized_pnl:.4f} USDT")
                            self.on_position_decreased(current_position, current_position, order_cache)
                                
            except ValueError as e:
                logger.error(f"❌ 订单数据验证失败: {e}")
                return
            except Exception as e:
                logger.error(f"❌ 处理订单数据时出错: {e}")
                return
            
        except Exception as e:
            logger.error(f"处理订单更新失败: {e}", exc_info=True)
    
    def get_all_positions(self) -> List[Position]:
        return [pos for pos in self.positions.values() if not pos.is_empty()]
    
    def get_position(self, symbol: str, position_side: str = 'BOTH') -> Optional[Position]:
        key = self._get_position_key(symbol, position_side)
        position = self.positions.get(key)
        return position if position and not position.is_empty() else None
    
    def get_total_unrealized_pnl(self) -> float:
        return sum(pos.unrealized_pnl for pos in self.get_all_positions())
