#!/bin/bash
# 停止币安监控程序

# 设置工作目录
cd /home/ubuntu/yanker/binance_monitor

# 检查supervisor是否在运行
if [ -f "supervisord.pid" ]; then
    PID=$(cat supervisord.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "正在停止币安监控程序..."
        supervisorctl -c supervisord.conf shutdown
        sleep 2
        
        # 检查是否已停止
        if ps -p $PID > /dev/null 2>&1; then
            echo "强制停止进程..."
            kill -TERM $PID
            sleep 2
            if ps -p $PID > /dev/null 2>&1; then
                echo "强制杀死进程..."
                kill -KILL $PID
            fi
        fi
        
        echo "✅ 币安监控程序已停止"
    else
        echo "程序未运行"
        rm -f supervisord.pid
    fi
else
    echo "程序未运行"
fi
