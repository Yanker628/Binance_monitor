"""仓位监控模块"""
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime

# 使用主程序的 logger
logger = logging.getLogger('binance_monitor')


class Position:
    """仓位数据类"""
    
    def __init__(self, data: Dict):
        self.symbol = data.get('symbol', '')
        self.position_side = data.get('positionSide', 'BOTH')
        self.position_amt = float(data.get('positionAmt', 0))
        self.entry_price = float(data.get('entryPrice', 0))
        self.mark_price = float(data.get('markPrice', 0))
        self.unrealized_pnl = float(data.get('unRealizedProfit', 0))
        self.leverage = int(data.get('leverage', 1))
        self.notional = float(data.get('notional', 0))
        self.isolated = data.get('isolated', False)
        self.update_time = datetime.now()
    
    def is_empty(self) -> bool:
        """判断是否为空仓"""
        return abs(self.position_amt) < 0.0001
    
    def get_side(self) -> str:
        """获取持仓方向"""
        if self.position_amt > 0:
            return 'LONG'
        elif self.position_amt < 0:
            return 'SHORT'
        else:
            return 'NONE'
    
    def get_pnl_percent(self) -> float:
        """计算PNL百分比"""
        if self.entry_price > 0:
            return (self.unrealized_pnl / abs(self.notional)) * 100 if self.notional != 0 else 0
        return 0
    
    def to_dict(self) -> Dict:
        """转换为字典"""
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
        self.leverage_cache: Dict[str, int] = {}  # 缓存杠杆信息
        self.on_position_opened: Optional[Callable] = None
        self.on_position_closed: Optional[Callable] = None
        self.on_position_increased: Optional[Callable] = None
        self.on_position_decreased: Optional[Callable] = None
    
    def _calculate_leverage(self, symbol: str, position_amt: float, entry_price: float, unrealized_pnl: float) -> int:
        """通过盈亏计算杠杆倍数"""
        if abs(position_amt) < 0.0001 or entry_price <= 0:
            return self.leverage_cache.get(symbol, 1)
        
        # 计算名义价值
        notional = abs(position_amt * entry_price)
        
        # 通过盈亏反推杠杆：PNL = position_amt * (mark_price - entry_price)
        # 如果PNL为0，说明mark_price = entry_price，无法计算杠杆
        if abs(unrealized_pnl) < 0.01:
            return self.leverage_cache.get(symbol, 1)
        
        # 计算当前标记价格
        mark_price = unrealized_pnl / position_amt + entry_price
        
        # 计算价格变化百分比
        price_change_pct = abs(mark_price - entry_price) / entry_price
        
        # 计算PNL百分比
        pnl_pct = abs(unrealized_pnl) / notional
        
        # 杠杆 = PNL百分比 / 价格变化百分比
        if price_change_pct > 0:
            calculated_leverage = int(round(pnl_pct / price_change_pct))
            # 限制在合理范围内
            calculated_leverage = max(1, min(calculated_leverage, 125))
            
            # 缓存杠杆信息
            self.leverage_cache[symbol] = calculated_leverage
            return calculated_leverage
        
        return self.leverage_cache.get(symbol, 1)
    
    def _get_position_key(self, symbol: str, position_side: str = 'BOTH') -> str:
        return f"{symbol}_{position_side}"
    
    def _create_position_dict(self, position: Position) -> Dict:
        """创建仓位数据字典，用于传递给聚合器"""
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
        """更新所有仓位信息"""
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
                    # 在平仓时，保存平仓前的完整仓位信息
                    if self.on_position_closed:
                        self.on_position_closed(old_position)
                    self.positions[key] = position
    
    def handle_account_update(self, event_data: Dict):
        """处理账户更新事件"""
        try:
            logger.info(f"🔄 处理账户更新事件")
            if event_data.get('e') != 'ACCOUNT_UPDATE':
                logger.warning(f"⚠️ 事件类型不是 ACCOUNT_UPDATE: {event_data.get('e')}")
                return
            
            positions_data = event_data.get('a', {}).get('P', [])
            logger.info(f"📊 收到 {len(positions_data)} 个仓位更新")
            
            for pos_data in positions_data:
                symbol = pos_data.get('s', '')
                position_side = pos_data.get('ps', 'BOTH')
                position_amt = float(pos_data.get('pa', 0))
                entry_price = float(pos_data.get('ep', 0))
                unrealized_pnl = float(pos_data.get('up', 0))
                
                logger.debug(f"📦 原始数据 {symbol}: pa={position_amt}, ep={entry_price}, up={unrealized_pnl}")
                
                key = self._get_position_key(symbol, position_side)
                old_position = self.positions.get(key)
                
                mark_price = 0
                notional = 0
                if abs(position_amt) > 0.0001 and entry_price > 0:
                    mark_price = unrealized_pnl / position_amt + entry_price
                    notional = abs(position_amt * mark_price)
                elif old_position and not old_position.is_empty():
                    mark_price = old_position.mark_price
                
                # 计算杠杆倍数
                leverage = self._calculate_leverage(symbol, position_amt, entry_price, unrealized_pnl)
                
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
                
                position = Position(position_data)
                
                if abs(position_amt) > 0.0001:
                    if old_position is None or old_position.is_empty():
                        self.positions[key] = position
                        if self.on_position_opened:
                            self.on_position_opened(position)
                    else:
                        old_amt = abs(old_position.position_amt)
                        new_amt = abs(position_amt)
                        
                        if new_amt > old_amt and self.on_position_increased:
                            self.on_position_increased(position, old_position)
                        elif new_amt < old_amt and self.on_position_decreased:
                            self.on_position_decreased(position, old_position)
                        
                        self.positions[key] = position
                else:
                    # 平仓：保存平仓前的完整信息传给回调
                    if old_position and not old_position.is_empty():
                        if self.on_position_closed:
                            # 关键修复：传递平仓前的旧仓位数据，包含正确的unrealized_pnl
                            self.on_position_closed(old_position)
                    self.positions[key] = position
                    
        except Exception as e:
            logger.error(f"处理账户更新失败: {e}", exc_info=True)
    
    def handle_order_update(self, event_data: Dict):
        """处理订单更新事件"""
        try:
            logger.info(f"🔄 处理订单更新事件")
            if event_data.get('e') != 'ORDER_TRADE_UPDATE':
                logger.warning(f"⚠️ 事件类型不是 ORDER_TRADE_UPDATE: {event_data.get('e')}")
                return
            
            order_data = event_data.get('o', {})
            symbol = order_data.get('s', '')
            order_status = order_data.get('X', '')
            order_side = order_data.get('S', '')  # BUY/SELL
            order_type = order_data.get('o', '')   # MARKET/LIMIT
            executed_qty = float(order_data.get('z', 0))
            avg_price = float(order_data.get('ap', 0))
            cum_quote = float(order_data.get('Z', 0))
            commission = float(order_data.get('n', 0))
            
            logger.debug(f"📦 订单数据 {symbol}: 状态={order_status}, 方向={order_side}, 数量={executed_qty}, 均价={avg_price}")
            
            # 只处理已成交的订单
            if order_status in ['FILLED', 'PARTIALLY_FILLED'] and executed_qty > 0:
                if order_side == 'SELL' and order_type == 'MARKET':
                    key = self._get_position_key(symbol, 'BOTH')
                    old_position = self.positions.get(key)
                    
                    if old_position and not old_position.is_empty():
                        entry_price = old_position.entry_price
                        close_price = avg_price
                        quantity = executed_qty
                        
                        actual_pnl = quantity * (close_price - entry_price)
                        
                        logger.info(f"💰 [{symbol}] 平仓订单成交: {quantity} @ {close_price}, 实际盈亏: {actual_pnl:.2f} USDT")
                        
                        if not hasattr(self, 'order_pnl_cache'):
                            self.order_pnl_cache = {}
                        
                        # 累计平仓数据
                        if key in self.order_pnl_cache:
                            # 已有数据，累计计算
                            existing = self.order_pnl_cache[key]
                            total_quantity = existing['total_quantity'] + quantity
                            total_cost = existing['total_cost'] + (quantity * close_price)
                            total_pnl = existing['total_pnl'] + actual_pnl
                            avg_close_price = total_cost / total_quantity
                            
                            self.order_pnl_cache[key] = {
                                'actual_pnl': total_pnl,
                                'close_price': avg_close_price,
                                'quantity': quantity,  # 当前单次成交数量
                                'total_quantity': total_quantity,  # 累计成交数量
                                'total_cost': total_cost,  # 累计成交金额
                                'entry_price': entry_price
                            }
                        else:
                            # 首次平仓
                            self.order_pnl_cache[key] = {
                                'actual_pnl': actual_pnl,
                                'close_price': close_price,
                                'quantity': quantity,
                                'total_quantity': quantity,
                                'total_cost': quantity * close_price,
                                'entry_price': entry_price
                            }
            
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
