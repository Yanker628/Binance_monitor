"""消息格式化工具"""
from typing import List, Dict, Optional
from datetime import datetime


def get_token_name(symbol: str) -> str:
    """从交易对中提取token名称"""
    if symbol.endswith('USDT'):
        return symbol[:-4]  # 去掉USDT后缀
    elif symbol.endswith('BUSD'):
        return symbol[:-4]  # 去掉BUSD后缀
    elif symbol.endswith('BTC'):
        return symbol[:-3]  # 去掉BTC后缀
    elif symbol.endswith('ETH'):
        return symbol[:-3]  # 去掉ETH后缀
    else:
        return symbol  # 如果无法识别，返回原符号


def get_price_precision(price: float) -> int:
    """获取价格精度，与币安保持一致"""
    if price >= 1000:
        return 2  # 高价币种2位小数
    elif price >= 1:
        return 4  # 中价币种4位小数
    else:
        return 6  # 低价币种6位小数


def get_side_text(position) -> str:
    """获取仓位方向文本"""
    return "做多" if position.get_side() == "LONG" else "做空"


def get_pnl_emoji(pnl: float) -> str:
    """获取盈亏表情符号"""
    return "📈" if pnl >= 0 else "📉"


def get_realized_pnl_emoji(pnl: float) -> str:
    """获取实现盈亏表情符号"""
    return "💰" if pnl >= 0 else "💸"


def format_timestamp(timestamp: datetime = None) -> str:
    """格式化时间戳"""
    if timestamp is None:
        timestamp = datetime.now()
    return timestamp.strftime('%Y-%m-%d %H:%M:%S')


def format_open_position_message(position) -> str:
    side_text = get_side_text(position)
    notional = abs(position.notional)
    pnl = position.unrealized_pnl
    
    entry_precision = get_price_precision(position.entry_price)
    pnl_emoji = get_pnl_emoji(pnl)
    
    token_name = get_token_name(position.symbol)
    message = (
        f"🚀 <b>开仓成功</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <code>{position.symbol}</code> <b>{side_text}</b>\n"
        f"💵 仓位价值: <b>{notional:.1f} USDT</b>\n"
        f"🔢 仓位数量: <b>{abs(position.position_amt):.0f} {token_name}</b>\n"
        f"💲 成交均价: <b>{position.entry_price:.{entry_precision}f} USDT</b>\n"
        f"{pnl_emoji} 浮动盈亏: <b>{pnl:.1f} USDT</b>\n"
        f"⏰ <b>{format_timestamp(position.update_time)}</b>"
    )
    
    return message


def format_increase_position_message(new_position, old_position) -> str:
    side_text = get_side_text(new_position)
    
    old_amt = abs(old_position.position_amt)
    new_amt = abs(new_position.position_amt)
    increase_amt = new_amt - old_amt
    increase_percent = (increase_amt / old_amt) * 100
    
    old_notional = abs(old_position.notional)
    new_notional = abs(new_position.notional)
    old_entry = old_position.entry_price
    new_entry = new_position.entry_price
    pnl = new_position.unrealized_pnl
    
    old_precision = get_price_precision(old_entry)
    new_precision = get_price_precision(new_entry)
    max_precision = max(old_precision, new_precision)
    pnl_emoji = get_pnl_emoji(pnl)
    
    token_name = get_token_name(new_position.symbol)
    message = (
        f"➕ <b>加仓 {increase_percent:.1f}%</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <code>{new_position.symbol}</code> <b>{side_text}</b>\n"
        f"🔢 仓位变化: <b>{old_amt:.0f} → {new_amt:.0f} {token_name}</b>\n"
        f"💵 仓位价值: <b>{old_notional:.1f} → {new_notional:.1f} USDT</b>\n"
        f"💲 加权均价: <b>{new_entry:.{max_precision}f} USDT</b>\n"
        f"📊 均价变化: <b>{old_entry:.{max_precision}f} → {new_entry:.{max_precision}f} USDT</b>\n"
        f"{pnl_emoji} 浮动盈亏: <b>{pnl:.1f} USDT</b>\n"
        f"⏰ <b>{format_timestamp(new_position.update_time)}</b>"
    )
    
    return message


def format_decrease_position_message(new_position, old_position, order_cache: Optional[Dict] = None) -> str:
    # 减仓时使用old_position的方向，因为new_position可能数量为0
    if old_position:
        side_text = get_side_text(old_position)
    else:
        side_text = get_side_text(new_position)
    
    old_amt = abs(old_position.position_amt)
    new_amt = abs(new_position.position_amt)
    decrease_amt = old_amt - new_amt
    decrease_percent = (decrease_amt / old_amt) * 100
    
    old_notional = abs(old_position.notional)
    new_notional = abs(new_position.notional)
    pnl = new_position.unrealized_pnl
    
    entry_precision = get_price_precision(new_position.entry_price)
    pnl_emoji = get_pnl_emoji(pnl)
    
    token_name = get_token_name(new_position.symbol)
    message = (
        f"➖ <b>减仓 {decrease_percent:.1f}%</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <code>{new_position.symbol}</code> <b>{side_text}</b>\n"
        f"🔢 仓位变化: <b>{old_amt:.0f} → {new_amt:.0f} {token_name}</b>\n"
        f"💵 仓位价值: <b>{old_notional:.1f} → {new_notional:.1f} USDT</b>\n"
    )
    
    if order_cache and 'actual_pnl' in order_cache:
        realized_pnl = order_cache['actual_pnl']
        pnl_emoji_realized = get_realized_pnl_emoji(realized_pnl)
        message += f"{pnl_emoji_realized} 本次盈亏: <b>{realized_pnl:.1f} USDT</b>\n"
        
    message += (
        f"💲 当前均价: <b>{new_position.entry_price:.{entry_precision}f} USDT</b>\n"
        f"{pnl_emoji} 浮动盈亏: <b>{pnl:.1f} USDT</b>\n"
        f"⏰ <b>{format_timestamp()}</b>"
    )
    
    return message


def format_close_position_message(position, old_position=None, order_cache: Optional[Dict] = None) -> str:
    # 平仓时使用old_position的方向，因为position.position_amt为0
    if old_position:
        side_text = get_side_text(old_position)
    else:
        side_text = get_side_text(position)
    
    if old_position:
        # 优先使用初始仓位信息（交易聚合数据），如果没有则使用当前old_position
        if hasattr(old_position, 'initial_position') and old_position.initial_position:
            initial_pos = old_position.initial_position
            old_notional = abs(initial_pos.notional)
            old_amount = abs(initial_pos.position_amt)
            # 检查是否是聚合数据（通过检查是否有聚合标识）
            is_aggregated = hasattr(initial_pos, 'is_aggregated') or abs(initial_pos.notional) > abs(old_position.notional) * 2
        else:
            old_notional = abs(old_position.notional)
            old_amount = abs(old_position.position_amt)
            is_aggregated = False
    else:
        old_notional = abs(position.notional)
        old_amount = 0.0
        is_aggregated = False
        
    if order_cache:
        pnl = order_cache.get('actual_pnl', 0.0)
        avg_price = order_cache.get('close_price', position.entry_price)
        pnl_source = "实际盈亏"
    else:
        pnl = position.unrealized_pnl
        avg_price = position.entry_price
        pnl_source = "预估盈亏"

    close_precision = get_price_precision(avg_price)
    pnl_emoji = get_realized_pnl_emoji(pnl)

    token_name = get_token_name(position.symbol)
    
    # 构建消息
    value_label = "交易总价值" if is_aggregated else "平仓前仓位"
    amount_label = "最大仓位" if is_aggregated else "仓位数量"
    
    message = (
        f"✅ <b>平仓完成</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <code>{position.symbol}</code> <b>{side_text}</b>\n"
        f"💵 {value_label}: <b>{old_notional:.1f} USDT</b>\n"
        f"🔢 {amount_label}: <b>{old_amount:.0f} {token_name}</b>\n"
        f"💲 平仓均价: <b>{avg_price:.{close_precision}f} USDT</b>\n"
        f"{pnl_emoji} {pnl_source}: <b>{pnl:.1f} USDT</b>\n"
        f"⏰ <b>{format_timestamp()}</b>"
    )
    
    return message
