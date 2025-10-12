#!/bin/bash
# 检查币安监控程序状态

# 设置工作目录
cd /home/ubuntu/yanker/binance_monitor

echo "🔍 币安监控程序状态检查"
echo "=" * 50

# 检查supervisor进程
if [ -f "supervisord.pid" ]; then
    PID=$(cat supervisord.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Supervisor运行中 (PID: $PID)"
        
        # 检查程序状态
        echo ""
        echo "📊 程序状态:"
        supervisorctl -c supervisord.conf status
        
        # 显示最近日志
        echo ""
        echo "📝 最近日志 (最后10行):"
        echo "-" * 50
        tail -10 logs/app_stdout.log
        
    else
        echo "❌ Supervisor进程不存在"
        rm -f supervisord.pid
    fi
else
    echo "❌ Supervisor未运行"
fi

echo ""
echo "📋 管理命令:"
echo "  启动: ./start.sh"
echo "  停止: ./stop.sh"
echo "  状态: ./status.sh"
echo "  日志: tail -f logs/app_stdout.log"
echo "  重启: supervisorctl -c supervisord.conf restart binance_monitor"
