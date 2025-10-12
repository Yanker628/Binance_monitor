#!/bin/bash
# 币安监控系统服务脚本

# 设置工作目录
WORK_DIR="/home/ubuntu/yanker/binance_monitor"
SERVICE_NAME="binance_monitor"

case "$1" in
    start)
        echo "启动币安监控服务..."
        cd $WORK_DIR
        ./start.sh
        ;;
    stop)
        echo "停止币安监控服务..."
        cd $WORK_DIR
        ./stop.sh
        ;;
    restart)
        echo "重启币安监控服务..."
        cd $WORK_DIR
        ./stop.sh
        sleep 2
        ./start.sh
        ;;
    status)
        echo "检查币安监控服务状态..."
        cd $WORK_DIR
        ./status.sh
        ;;
    enable)
        echo "设置开机自启动..."
        # 创建systemd服务文件
        sudo tee /etc/systemd/system/binance-monitor.service > /dev/null <<EOF
[Unit]
Description=Binance Monitor Service
After=network.target

[Service]
Type=forking
User=ubuntu
WorkingDirectory=$WORK_DIR
ExecStart=$WORK_DIR/start.sh
ExecStop=$WORK_DIR/stop.sh
ExecReload=$WORK_DIR/restart.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload
        sudo systemctl enable binance-monitor.service
        echo "✅ 开机自启动已设置"
        ;;
    disable)
        echo "禁用开机自启动..."
        sudo systemctl disable binance-monitor.service
        echo "✅ 开机自启动已禁用"
        ;;
    logs)
        echo "查看实时日志..."
        cd $WORK_DIR
        tail -f logs/app_stdout.log
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|enable|disable|logs}"
        echo ""
        echo "命令说明:"
        echo "  start    - 启动服务"
        echo "  stop     - 停止服务"
        echo "  restart  - 重启服务"
        echo "  status   - 查看状态"
        echo "  enable   - 设置开机自启动"
        echo "  disable  - 禁用开机自启动"
        echo "  logs     - 查看实时日志"
        exit 1
        ;;
esac
