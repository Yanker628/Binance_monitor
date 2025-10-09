# 币安合约持仓监控机器人

一个功能强大的币安 (Binance) 合约持仓监控机器人，可通过 Telegram 实时推送开仓、平仓、加仓、减仓等关键事件通知。

该项目基于 WebSocket 实现低延迟的事件捕获，并设计了健壮的运行机制，确保长期稳定运行。

## 主要特性

- **实时监控**: 基于 Binance WebSocket API，实现低延迟的账户和持仓事件捕获。
- **多账户支持**: 可同时监控**标准合约账户**和**统一账户**，并在通知中明确区分。
- **聚合通知**: 能将短时间内的多次仓位变化（如快速的部分平仓）智能地聚合成一条消息，有效避免消息轰炸。
- **强大的通知系统**: 通过 Telegram Bot 推送格式化、易于阅读的通知，并支持配置多个机器人同时推送到不同频道。
- **稳健的运行机制**:
    - **进程守护**: 推荐使用 `supervisor` 进行进程守护，实现程序崩溃后自动重启。
    - **优雅停机/重启**: 程序能响应 `SIGTERM` 和 `SIGUSR1` 信号，在关闭或重启前完成清理工作（如关闭WebSocket、删除ListenKey），保证状态一致。
- **灵活的配置**: 所有敏感信息和应用配置均通过 `.env` 文件进行管理，安全且便于修改。

## 项目结构

```
/home/ubuntu/yanker/binance_monitor/
├───.env.example           # 环境变量配置示例
├───.gitignore             # Git忽略文件配置
├───main.py                # 主程序入口
├───README.md              # 项目说明文档
├───requirements.txt       # Python依赖包
├───supervisord.conf       # Supervisor配置文件
├───binance/               # 币安API和WebSocket客户端
├───config/                # 配置加载和管理
├───logs/                  # 日志文件目录
├───monitor/               # 持仓监控逻辑
├───notifier/              # Telegram通知和消息聚合
└───utils/                 # 通用工具（日志、格式化等）
```

## 安装与配置

### 1. 克隆项目
```bash
git clone https://github.com/Yanker628/binance_monitor.git
cd binance_monitor
```

### 2. 创建并激活虚拟环境
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖
项目使用 `uv` 作为包管理器以获得更快的安装速度，您也可以使用 `pip`。
```bash
# 使用 uv (推荐)
uv pip install -r requirements.txt

# 或者使用 pip
pip install -r requirements.txt
```

### 4. 配置环境变量
复制示例文件并根据您的实际情况修改。
```bash
cp .env.example .env
```
然后编辑 `.env` 文件，填入您的币安 API 密钥和 Telegram Bot 信息。

**`.env` 文件详解:**
- `BINANCE_FUTURES_ENABLED`: 是否启用标准合约账户 (True/False)。
- `BINANCE_API_KEY`, `BINANCE_API_SECRET`: 标准合约账户的 API Key 和 Secret。
- `BINANCE_UNIFIED_ENABLED`: 是否启用统一账户 (True/False)。
- `BINANCE_UNIFIED_API_KEY`, `BINANCE_UNIFIED_API_SECRET`: 统一账户的 API Key 和 Secret。
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: 第一个 Telegram Bot 的 Token 和目标频道的 Chat ID。
- `TELEGRAM_TOPIC_ID`: (可选) 如果频道开启了话题(Topic)功能，可指定消息发送到的话题ID。
- `TELEGRAM_BOT_TOKEN_2`, `TELEGRAM_CHAT_ID_2`: (可选) 配置第二个机器人。
- `LOG_LEVEL`: 日志级别 (如 `INFO`, `DEBUG`)。
- `MESSAGE_AGGREGATION_WINDOW_MS`: 消息聚合的时间窗口（毫秒）。
- `LISTEN_KEY_KEEPALIVE_INTERVAL`: ListenKey 的保活间隔（秒），建议值 `1200` (20分钟)。

## 使用方法

### 开发模式 (手动运行)
直接运行主程序，用于调试和快速测试。按 `Ctrl+C` 停止。
```bash
python main.py
```

### 生产模式 (使用 Supervisor)
这是推荐的长期运行方式，可以保证程序稳定可靠。

**1. 启动 Supervisor:**
使用项目中的配置文件启动 `supervisord` 守护进程。
```bash
supervisord -c supervisord.conf
```

**2. 管理应用:**
使用 `supervisorctl` 来管理您的监控程序。
```bash
# 查看应用状态
supervisorctl status binance_monitor

# 停止应用
supervisorctl stop binance_monitor

# 启动应用
supervisorctl start binance_monitor

# 重启应用 (更新代码后使用此命令)
supervisorctl restart binance_monitor

# 查看实时日志
supervisorctl tail -f binance_monitor stdout
```

## 高级功能

### 手动平滑重启
在**手动运行**模式下，您可以通过发送 `SIGUSR1` 信号来触发程序的平滑重启，这对于不中断服务的情况下更新代码非常有用。

```bash
# 1. 找到 main.py 的进程ID (PID)
pgrep -f "python main.py"

# 2. 发送重启信号
kill -SIGUSR1 <PID>
```
程序会执行优雅停机，然后通过 `os.execv` 重新加载并启动。在 `supervisor` 模式下，请使用 `supervisorctl restart` 命令。

## 📝 许可证

MIT License
