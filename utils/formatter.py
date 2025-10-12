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


def format_open_position_message(position) -> str:
    side_text = "做多" if position.get_side() == "LONG" else "做空"
    notional = abs(position.notional)
    pnl = position.unrealized_pnl
    
    # 动态确定价格精度
    def get_price_precision(price):
        if price == 0:
            return 4
        price_str = f"{price:.10f}".rstrip('0')
        if '.' in price_str:
            return len(price_str.split('.')[1])
        return 4
    
    entry_precision = get_price_precision(position.entry_price)
    pnl_emoji = "📈" if pnl >= 0 else "📉"
    
    token_name = get_token_name(position.symbol)
    message = (
        f"🚀 <b>开仓成功</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <code>{position.symbol}</code> <b>{side_text}</b>\n"
        f"💵 仓位价值: <b>{notional:.2f} USDT</b>\n"
        f"🔢 仓位数量: <b>{abs(position.position_amt):.0f} {token_name}</b>\n"
        f"💲 成交均价: <b>{position.entry_price:.{entry_precision}f} USDT</b>\n"
        f"{pnl_emoji} 浮动盈亏: <b>{pnl:.2f} USDT</b>\n"
        f"⏰ <b>{position.update_time.strftime('%Y-%m-%d %H:%M:%S')}</b>"
    )
    
    return message


def format_increase_position_message(new_position, old_position) -> str:
    side_text = "做多" if new_position.get_side() == "LONG" else "做空"
    
    old_amt = abs(old_position.position_amt)
    new_amt = abs(new_position.position_amt)
    increase_amt = new_amt - old_amt
    increase_percent = (increase_amt / old_amt) * 100
    
    old_notional = abs(old_position.notional)
    new_notional = abs(new_position.notional)
    old_entry = old_position.entry_price
    new_entry = new_position.entry_price
    pnl = new_position.unrealized_pnl
    
    # 动态确定价格精度
    def get_price_precision(price):
        if price == 0:
            return 4
        price_str = f"{price:.10f}".rstrip('0')
        if '.' in price_str:
            return len(price_str.split('.')[1])
        return 4
    
    old_precision = get_price_precision(old_entry)
    new_precision = get_price_precision(new_entry)
    max_precision = max(old_precision, new_precision, 4)
    pnl_emoji = "📈" if pnl >= 0 else "📉"
    
    token_name = get_token_name(new_position.symbol)
    message = (
        f"➕ <b>加仓 {increase_percent:.2f}%</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <code>{new_position.symbol}</code> <b>{side_text}</b>\n"
        f"🔢 仓位变化: <b>{old_amt:.0f} → {new_amt:.0f} {token_name}</b>\n"
        f"💵 仓位价值: <b>{old_notional:.2f} → {new_notional:.2f} USDT</b>\n"
        f"💲 加权均价: <b>{new_entry:.{max_precision}f} USDT</b>\n"
        f"📊 均价变化: <b>{old_entry:.{max_precision}f} → {new_entry:.{max_precision}f} USDT</b>\n"
        f"{pnl_emoji} 浮动盈亏: <b>{pnl:.2f} USDT</b>\n"
        f"⏰ <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>"
    )
    
    return message


def format_decrease_position_message(new_position, old_position, order_cache: Optional[Dict] = None) -> str:
    # 减仓时使用old_position的方向，因为new_position可能数量为0
    if old_position:
        side_text = "做多" if old_position.get_side() == "LONG" else "做空"
    else:
        side_text = "做多" if new_position.get_side() == "LONG" else "做空"
    
    old_amt = abs(old_position.position_amt)
    new_amt = abs(new_position.position_amt)
    decrease_amt = old_amt - new_amt
    decrease_percent = (decrease_amt / old_amt) * 100
    
    old_notional = abs(old_position.notional)
    new_notional = abs(new_position.notional)
    pnl = new_position.unrealized_pnl
    
    # 动态确定价格精度
    def get_price_precision(price):
        if price == 0:
            return 4
        price_str = f"{price:.10f}".rstrip('0')
        if '.' in price_str:
            return len(price_str.split('.')[1])
        return 4
    
    entry_precision = get_price_precision(new_position.entry_price)
    pnl_emoji = "📈" if pnl >= 0 else "📉"
    
    token_name = get_token_name(new_position.symbol)
    message = (
        f"➖ <b>减仓 {decrease_percent:.2f}%</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <code>{new_position.symbol}</code> <b>{side_text}</b>\n"
        f"🔢 仓位变化: <b>{old_amt:.0f} → {new_amt:.0f} {token_name}</b>\n"
        f"💵 仓位价值: <b>{old_notional:.2f} → {new_notional:.2f} USDT</b>\n"
    )
    
    if order_cache and 'actual_pnl' in order_cache:
        realized_pnl = order_cache['actual_pnl']
        pnl_emoji_realized = "💰" if realized_pnl >= 0 else "💸"
        message += f"{pnl_emoji_realized} 本次盈亏: <b>{realized_pnl:.2f} USDT</b>\n"
        
    message += (
        f"💲 当前均价: <b>{new_position.entry_price:.{entry_precision}f} USDT</b>\n"
        f"{pnl_emoji} 浮动盈亏: <b>{pnl:.2f} USDT</b>\n"
        f"⏰ <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>"
    )
    
    return message


def format_close_position_message(position, old_position=None, order_cache: Optional[Dict] = None) -> str:
    # 平仓时使用old_position的方向，因为position.position_amt为0
    if old_position:
        side_text = "做多" if old_position.get_side() == "LONG" else "做空"
    else:
        side_text = "做多" if position.get_side() == "LONG" else "做空"
    
    if old_position:
        old_notional = abs(old_position.notional)
        old_amount = abs(old_position.position_amt)
    else:
        old_notional = abs(position.notional)
        old_amount = 0.0
        
    if order_cache:
        pnl = order_cache.get('actual_pnl', 0.0)
        avg_price = order_cache.get('close_price', position.entry_price)
        pnl_source = "实际盈亏"
    else:
        pnl = position.unrealized_pnl
        avg_price = position.entry_price
        pnl_source = "预估盈亏"

    # 动态确定价格精度
    def get_price_precision(price):
        if price == 0:
            return 4
        price_str = f"{price:.10f}".rstrip('0')
        if '.' in price_str:
            return len(price_str.split('.')[1])
        return 4
    
    close_precision = get_price_precision(avg_price)
    pnl_emoji = "💰" if pnl >= 0 else "💸"

    token_name = get_token_name(position.symbol)
    message = (
        f"✅ <b>平仓完成</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <code>{position.symbol}</code> <b>{side_text}</b>\n"
        f"💵 平仓前仓位: <b>{old_notional:.2f} USDT</b>\n"
        f"🔢 仓位数量: <b>{old_amount:.0f} {token_name}</b>\n"
        f"💲 平仓均价: <b>{avg_price:.{close_precision}f} USDT</b>\n"
        f"{pnl_emoji} {pnl_source}: <b>{pnl:.2f} USDT</b>\n"
        f"⏰ <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>"
    )
    
    return message
