#!/bin/bash
# 静默启动币安监控程序

# 设置工作目录
cd /home/ubuntu/yanker/binance_monitor

# 检查supervisor是否已运行
if [ -f "supervisord.pid" ]; then
    PID=$(cat supervisord.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Supervisor已在运行 (PID: $PID)"
        echo "使用以下命令管理:"
        echo "  查看状态: supervisorctl -c supervisord.conf status"
        echo "  重启程序: supervisorctl -c supervisord.conf restart binance_monitor"
        echo "  停止程序: supervisorctl -c supervisord.conf stop binance_monitor"
        echo "  查看日志: tail -f logs/app_stdout.log"
        exit 0
    else
        echo "清理旧的PID文件..."
        rm -f supervisord.pid
    fi
fi

# 创建日志目录
mkdir -p logs

# 静默启动supervisor
echo "正在启动币安监控程序..."
supervisord -c supervisord.conf

# 等待启动
sleep 2

# 检查启动状态
if [ -f "supervisord.pid" ]; then
    PID=$(cat supervisord.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ 币安监控程序已成功启动 (PID: $PID)"
        echo ""
        echo "📋 管理命令:"
        echo "  查看状态: supervisorctl -c supervisord.conf status"
        echo "  重启程序: supervisorctl -c supervisord.conf restart binance_monitor"
        echo "  停止程序: supervisorctl -c supervisord.conf stop binance_monitor"
        echo "  查看日志: tail -f logs/app_stdout.log"
        echo "  停止服务: supervisorctl -c supervisord.conf shutdown"
        echo ""
        echo "📊 程序状态:"
        supervisorctl -c supervisord.conf status
    else
        echo "❌ 启动失败，请检查日志: logs/supervisord.log"
        exit 1
    fi
else
    echo "❌ 启动失败，请检查日志: logs/supervisord.log"
    exit 1
fi
