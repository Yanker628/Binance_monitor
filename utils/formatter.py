"""消息格式化工具"""
from typing import List, Dict, Optional
from datetime import datetime


def format_open_position_message(position) -> str:
    side_text = "做多" if position.get_side() == "LONG" else "做空"
    notional = abs(position.notional)
    
    # 浮动盈亏
    pnl = position.unrealized_pnl
    
    message = (
        f"🚀 开仓成功\n"
        f"• 币种: {position.symbol}\n"
        f"• 方向: {side_text}\n"
        f"• 当前仓位: {notional:.2f} USDT\n"
        f"• 仓位数量: {abs(position.position_amt):.6f}\n"
        f"• 成交均价: {position.entry_price:.4f}\n"
        f"• 浮动盈亏: {pnl:.2f}\n"
        f"• 时间: {position.update_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    return message


def format_increase_position_message(new_position, old_position) -> str:
    side_text = "做多" if new_position.get_side() == "LONG" else "做空"
    
    old_amt = abs(old_position.position_amt)
    new_amt = abs(new_position.position_amt)
    increase_amt = new_amt - old_amt
    increase_percent = (increase_amt / old_amt) * 100
    
    notional = abs(new_position.notional)
    
    # 均价变化
    old_entry = old_position.entry_price
    new_entry = new_position.entry_price
    
    # 浮动盈亏
    pnl = new_position.unrealized_pnl
    
    message = (
        f"➕ 加仓 {increase_percent:.2f}%\n"
        f"• 币种: {new_position.symbol}\n"
        f"• 方向: {side_text}\n"
        f"• 当前仓位: {notional:.2f} USDT\n"
        f"• 仓位数量: {new_amt:.6f}\n"
        f"• 加权均价: {new_entry:.4f}\n"
        f"• 均价变化: {old_entry:.4f} → {new_entry:.4f}\n"
        f"• 浮动盈亏: {pnl:.2f}\n"
        f"• 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    return message


def format_decrease_position_message(new_position, old_position) -> str:
    side_text = "做多" if new_position.get_side() == "LONG" else "做空"
    
    old_amt = abs(old_position.position_amt)
    new_amt = abs(new_position.position_amt)
    decrease_amt = old_amt - new_amt
    decrease_percent = (decrease_amt / old_amt) * 100
    
    notional = abs(new_position.notional)
    
    # 浮动盈亏
    pnl = new_position.unrealized_pnl
    
    message = (
        f"➖ 减仓 {decrease_percent:.2f}%\n"
        f"• 币种: {new_position.symbol}\n"
        f"• 方向: {side_text}\n"
        f"• 当前仓位: {notional:.2f} USDT\n"
        f"• 仓位数量: {new_amt:.6f}\n"
        f"• 当前均价: {new_position.entry_price:.4f}\n"
        f"• 浮动盈亏: {pnl:.2f}\n"
        f"• 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    return message


def format_close_position_message(position, old_position=None) -> str:
    side_text = "做多" if position.get_side() == "LONG" else "做空"
    
    # 如果有old_position，使用平仓前的仓位信息
    if old_position:
        old_notional = abs(old_position.notional)
        old_amount = abs(old_position.position_amt)
    else:
        old_notional = abs(position.notional)
        old_amount = 0.0
    
    pnl = position.unrealized_pnl
    avg_price = position.entry_price
    
    message = (
        f"✅ 平仓完成\n"
        f"• 币种: {position.symbol}\n"
        f"• 方向: {side_text}\n"
        f"• 平仓前仓位: {old_notional:.2f} USDT\n"
        f"• 仓位数量: {old_amount:.6f}\n"
        f"• 平仓均价: {avg_price:.4f}\n"
        f"• 累计盈亏: {pnl:.2f}\n"
        f"• 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    return message
