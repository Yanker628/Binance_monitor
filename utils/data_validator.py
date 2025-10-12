"""数据验证和安全模块"""
import re
import logging
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal, InvalidOperation

logger = logging.getLogger('binance_monitor')


class DataValidator:
    """数据验证器"""
    
    SYMBOL_PATTERN = re.compile(r'^[A-Z0-9]{1,10}USDT$')
    POSITION_SIDES = {'LONG', 'SHORT', 'BOTH'}
    ORDER_STATUSES = {'NEW', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'REJECTED', 'EXPIRED'}
    ORDER_TYPES = {'LIMIT', 'MARKET', 'STOP', 'STOP_MARKET', 'TAKE_PROFIT', 'TAKE_PROFIT_MARKET'}
    ORDER_SIDES = {'BUY', 'SELL'}
    
    @classmethod
    def validate_symbol(cls, symbol: str) -> bool:
        if not isinstance(symbol, str):
            logger.warning(f"交易对不是字符串类型: {type(symbol)}")
            return False
        
        if len(symbol) < 5 or len(symbol) > 20:
            logger.warning(f"交易对长度异常: {symbol} (长度: {len(symbol)})")
            return False
        
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '|', '`', '$']
        if any(char in symbol for char in dangerous_chars):
            logger.warning(f"交易对包含危险字符: {symbol}")
            return False
        
        if not cls.SYMBOL_PATTERN.match(symbol):
            logger.warning(f"无效的交易对格式: {symbol}")
            return False
        
        return True
    
    @classmethod
    def validate_position_side(cls, position_side: str) -> bool:
        if not isinstance(position_side, str):
            return False
        
        if position_side not in cls.POSITION_SIDES:
            logger.warning(f"无效的仓位方向: {position_side}")
            return False
        
        return True
    
    @classmethod
    def validate_numeric_value(cls, value: Any, field_name: str, 
                             min_val: Optional[float] = None, 
                             max_val: Optional[float] = None,
                             allow_zero: bool = True) -> Optional[float]:
        try:
            if isinstance(value, str):
                if not value.strip():
                    return 0.0 if allow_zero else None
                
                if len(value) > 50:
                    logger.warning(f"{field_name} 字符串过长: {len(value)} 字符")
                    return None
                
                import re
                if not re.match(r'^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$', value.strip()):
                    logger.warning(f"{field_name} 包含非数字字符: {value}")
                    return None
                
                float_val = float(value)
            elif isinstance(value, (int, float)):
                float_val = float(value)
            else:
                logger.warning(f"{field_name} 不是有效的数值类型: {type(value)}")
                return None
            
            if not isinstance(float_val, float) or float_val != float_val:
                logger.warning(f"{field_name} 包含无效数值: {value}")
                return None
            
            if abs(float_val) == float('inf'):
                logger.warning(f"{field_name} 值为无穷大: {value}")
                return None
            
            if min_val is not None and float_val < min_val:
                logger.warning(f"{field_name} 值过小: {float_val} < {min_val}")
                return None
            
            if max_val is not None and float_val > max_val:
                logger.warning(f"{field_name} 值过大: {float_val} > {max_val}")
                return None
            
            if not allow_zero and abs(float_val) < 1e-10:
                logger.warning(f"{field_name} 不允许为零值: {float_val}")
                return None
            
            return float_val
            
        except (ValueError, TypeError, InvalidOperation) as e:
            logger.warning(f"{field_name} 数值转换失败: {value}, 错误: {e}")
            return None
    
    @classmethod
    def validate_price(cls, price: Any, field_name: str = "价格") -> Optional[float]:
        return cls.validate_numeric_value(
            price, field_name, 
            min_val=0.0, 
            max_val=1000000.0,
            allow_zero=False
        )
    
    @classmethod
    def validate_quantity(cls, quantity: Any, field_name: str = "数量") -> Optional[float]:
        return cls.validate_numeric_value(
            quantity, field_name,
            min_val=-1000000.0,
            max_val=1000000.0,
            allow_zero=True
        )
    
    @classmethod
    def validate_pnl(cls, pnl: Any, field_name: str = "盈亏") -> Optional[float]:
        return cls.validate_numeric_value(
            pnl, field_name,
            min_val=-1000000.0,
            max_val=1000000.0,
            allow_zero=True
        )
    
    @classmethod
    def validate_leverage(cls, leverage: Any, field_name: str = "杠杆") -> Optional[int]:
        try:
            if isinstance(leverage, str):
                leverage = int(float(leverage))
            elif isinstance(leverage, float):
                leverage = int(leverage)
            elif not isinstance(leverage, int):
                logger.warning(f"{field_name} 不是有效的整数类型: {type(leverage)}")
                return None
            
            if leverage < 1 or leverage > 125:
                logger.warning(f"{field_name} 超出有效范围: {leverage}")
                return None
            
            return leverage
            
        except (ValueError, TypeError) as e:
            logger.warning(f"{field_name} 转换失败: {leverage}, 错误: {e}")
            return None
    
    @classmethod
    def validate_order_status(cls, status: str) -> bool:
        if not isinstance(status, str):
            return False
        
        if status not in cls.ORDER_STATUSES:
            logger.warning(f"无效的订单状态: {status}")
            return False
        
        return True
    
    @classmethod
    def validate_order_type(cls, order_type: str) -> bool:
        if not isinstance(order_type, str):
            return False
        
        if order_type not in cls.ORDER_TYPES:
            logger.warning(f"无效的订单类型: {order_type}")
            return False
        
        return True
    
    @classmethod
    def validate_order_side(cls, order_side: str) -> bool:
        if not isinstance(order_side, str):
            return False
        
        if order_side not in cls.ORDER_SIDES:
            logger.warning(f"无效的订单方向: {order_side}")
            return False
        
        return True


class SafeDataProcessor:
    """安全数据处理器"""
    
    @staticmethod
    def safe_float_conversion(value: Any, default: float = 0.0, field_name: str = "字段") -> float:
        try:
            if value is None:
                return default
            
            if isinstance(value, str):
                if not value.strip():
                    return default
                return float(value)
            
            return float(value)
            
        except (ValueError, TypeError) as e:
            logger.warning(f"{field_name} 转换失败: {value}, 使用默认值: {default}, 错误: {e}")
            return default
    
    @staticmethod
    def safe_int_conversion(value: Any, default: int = 0, field_name: str = "字段") -> int:
        try:
            if value is None:
                return default
            
            if isinstance(value, str):
                if not value.strip():
                    return default
                return int(float(value))
            
            return int(value)
            
        except (ValueError, TypeError) as e:
            logger.warning(f"{field_name} 转换失败: {value}, 使用默认值: {default}, 错误: {e}")
            return default
    
    @staticmethod
    def safe_string_conversion(value: Any, default: str = "", field_name: str = "字段") -> str:
        try:
            if value is None:
                return default
            
            return str(value).strip()
            
        except Exception as e:
            logger.warning(f"{field_name} 转换失败: {value}, 使用默认值: {default}, 错误: {e}")
            return default
    
    @staticmethod
    def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        
        for key, value in data.items():
            clean_key = str(key).strip()
            
            if len(clean_key) > 100:
                logger.warning(f"键名过长，已截断: {clean_key[:50]}...")
                clean_key = clean_key[:100]
            
            if isinstance(value, str):
                if len(value) > 10000:
                    logger.warning(f"字符串值过长，已截断: {len(value)} 字符")
                    value = value[:10000]
                
                clean_value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\t')
                
                dangerous_patterns = ['--', '/*', '*/', 'xp_', 'sp_', 'exec', 'execute']
                for pattern in dangerous_patterns:
                    if pattern.lower() in clean_value.lower():
                        logger.warning(f"检测到潜在危险模式: {pattern}")
                        clean_value = clean_value.replace(pattern, '')
            else:
                clean_value = value
            
            sanitized[clean_key] = clean_value
        
        return sanitized
    
    @staticmethod
    def validate_json_size(data: str, max_size: int = 1024 * 1024) -> bool:
        if len(data) > max_size:
            logger.warning(f"JSON数据过大: {len(data)} 字节，限制: {max_size} 字节")
            return False
        return True
    
    @staticmethod
    def validate_request_frequency(request_times: list, max_requests: int = 60, window_seconds: int = 60) -> bool:
        import time
        now = time.time()
        
        valid_times = [t for t in request_times if now - t < window_seconds]
        
        if len(valid_times) >= max_requests:
            logger.warning(f"请求频率过高: {len(valid_times)}/{max_requests} 在 {window_seconds} 秒内")
            return False
        
        return True


class PositionDataValidator:
    """仓位数据验证器"""
    
    @staticmethod
    def validate_position_data(data: Dict[str, Any]) -> Dict[str, Any]:
        validator = DataValidator()
        processor = SafeDataProcessor()
        
        symbol = processor.safe_string_conversion(data.get('symbol', ''), 'UNKNOWN', '交易对')
        if not validator.validate_symbol(symbol):
            raise ValueError(f"无效的交易对: {symbol}")
        
        position_side = processor.safe_string_conversion(data.get('positionSide', 'BOTH'), 'BOTH', '仓位方向')
        if not validator.validate_position_side(position_side):
            raise ValueError(f"无效的仓位方向: {position_side}")
        
        position_amt = validator.validate_quantity(data.get('positionAmt', 0), '仓位数量')
        if position_amt is None:
            raise ValueError("无效的仓位数量")
        
        position_amt = abs(position_amt) if position_amt is not None else 0
        if position_amt > 0.0001:
            entry_price = validator.validate_price(data.get('entryPrice', 0), '开仓价格')
            if entry_price is None:
                raise ValueError("无效的开仓价格")
        else:
            entry_price = validator.validate_numeric_value(
                data.get('entryPrice', 0), '开仓价格',
                min_val=0.0, max_val=1000000.0, allow_zero=True
            ) or 0.0
        
        unrealized_pnl = validator.validate_pnl(data.get('unRealizedProfit', 0), '浮动盈亏')
        if unrealized_pnl is None:
            raise ValueError("无效的浮动盈亏")
        
        leverage = validator.validate_leverage(data.get('leverage', 1), '杠杆')
        if leverage is None:
            raise ValueError("无效的杠杆")
        
        validated_data = {
            'symbol': symbol,
            'positionSide': position_side,
            'positionAmt': position_amt,
            'entryPrice': entry_price,
            'unRealizedProfit': unrealized_pnl,
            'leverage': leverage,
            'notional': processor.safe_float_conversion(data.get('notional', 0), 0, '名义价值'),
            'isolated': bool(data.get('isolated', False)),
            'markPrice': validator.validate_price(data.get('markPrice', entry_price), '标记价格') or entry_price
        }
        
        return validated_data
    
    @staticmethod
    def validate_order_data(data: Dict[str, Any]) -> Dict[str, Any]:
        validator = DataValidator()
        processor = SafeDataProcessor()
        
        symbol = processor.safe_string_conversion(data.get('s', ''), 'UNKNOWN', '交易对')
        if not validator.validate_symbol(symbol):
            raise ValueError(f"无效的交易对: {symbol}")
        
        order_status = processor.safe_string_conversion(data.get('X', ''), 'UNKNOWN', '订单状态')
        if not validator.validate_order_status(order_status):
            raise ValueError(f"无效的订单状态: {order_status}")
        
        order_side = processor.safe_string_conversion(data.get('S', ''), 'UNKNOWN', '订单方向')
        if not validator.validate_order_side(order_side):
            raise ValueError(f"无效的订单方向: {order_side}")
        
        order_type = processor.safe_string_conversion(data.get('o', ''), 'UNKNOWN', '订单类型')
        if not validator.validate_order_type(order_type):
            raise ValueError(f"无效的订单类型: {order_type}")

        position_side = processor.safe_string_conversion(data.get('ps', 'BOTH'), 'BOTH', '仓位方向')
        if not validator.validate_position_side(position_side):
            raise ValueError(f"无效的仓位方向: {position_side}")
        
        executed_qty = validator.validate_quantity(data.get('z', 0), '成交数量')
        if executed_qty is None:
            raise ValueError("无效的成交数量")
        
        realized_pnl = validator.validate_pnl(data.get('rp', 0), '实现盈亏')
        if realized_pnl is None:
            raise ValueError("无效的实现盈亏")

        # 根据订单状态决定是否允许平均价格为0
        # NEW, CANCELED, REJECTED, EXPIRED 状态的订单平均价格可以为0
        allow_zero_price = order_status in ['NEW', 'CANCELED', 'REJECTED', 'EXPIRED']
        
        if allow_zero_price:
            avg_price = validator.validate_numeric_value(
                data.get('ap', 0), '平均价格',
                min_val=0.0, max_val=1000000.0, allow_zero=True
            )
        else:
            avg_price = validator.validate_price(data.get('ap', 0), '平均价格')
        
        if avg_price is None:
            raise ValueError("无效的平均价格")
        
        validated_data = {
            's': symbol,
            'X': order_status,
            'S': order_side,
            'o': order_type,
            'ps': position_side,
            'z': executed_qty,
            'ap': avg_price,
            'rp': realized_pnl,
            'Z': processor.safe_float_conversion(data.get('Z', 0), 0, '累计成交金额'),
            'n': processor.safe_float_conversion(data.get('n', 0), 0, '手续费')
        }
        
        return validated_data
