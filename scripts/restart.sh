#!/bin/bash
# 重启币安监控程序

# 设置工作目录
cd /home/ubuntu/yanker/binance_monitor

echo "正在重启币安监控程序..."

# 停止程序
./scripts/stop.sh

# 等待停止
sleep 3

# 启动程序
./scripts/start.sh
