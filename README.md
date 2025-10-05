# 币安合约监控机器人 🤖

实时监控币安合约仓位变动，通过 Telegram Bot 推送通知。

## ✨ 功能特性

- **实时监控** - 开仓、平仓、加仓、减仓检测
- **智能聚合** - 多次快速操作自动合并为一条消息
- **双账户支持** - 标准合约账户和统一账户
- **准确盈亏** - 基于订单更新事件计算实际盈亏
- **多Bot推送** - 支持多个 Telegram Bot 和话题组

## 📱 消息格式

```
🚀 开仓成功
• 币种: BTCUSDT
• 方向: 做多
• 当前仓位: 200.00 USDT
• 仓位数量: 0.005000
• 成交均价: 40000.0000
• 浮动盈亏: 5.00
• 时间: 2025-10-05 22:17:25
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入配置：

```env
# 币安API配置
BINANCE_API_KEY=你的API_KEY
BINANCE_API_SECRET=你的API_SECRET

# Telegram Bot配置
TELEGRAM_BOT_TOKEN=你的bot_token
TELEGRAM_CHAT_ID=你的chat_id
TELEGRAM_TOPIC_ID=30
```

### 3. 运行程序

```bash
python3 main.py
```

## 📁 项目结构

```
binance_monitor/
├── main.py              # 主程序入口
├── config/              # 配置管理
├── binance/             # 币安API模块
├── monitor/             # 仓位监控
├── notifier/            # 消息通知
└── utils/               # 工具函数
```

## ⚙️ 配置说明

### 币安账户配置

**标准合约账户（可选）**
```env
BINANCE_FUTURES_ENABLED=True
BINANCE_API_KEY=你的API_KEY
BINANCE_API_SECRET=你的API_SECRET
```

**统一账户（可选）**
```env
BINANCE_UNIFIED_ENABLED=True
BINANCE_UNIFIED_API_KEY=你的统一账户API_KEY
BINANCE_UNIFIED_API_SECRET=你的统一账户API_SECRET
```

### Telegram Bot配置

**主Bot（必填）**
```env
TELEGRAM_BOT_TOKEN=你的bot_token
TELEGRAM_CHAT_ID=你的chat_id
TELEGRAM_TOPIC_ID=30
```

**第二个Bot（可选）**
```env
TELEGRAM_BOT_TOKEN_2=你的第二个bot_token
TELEGRAM_CHAT_ID_2=你的第二个chat_id
TELEGRAM_TOPIC_ID_2=
```

### 应用配置

```env
LOG_LEVEL=INFO
MESSAGE_AGGREGATION_WINDOW_MS=1000
LISTEN_KEY_KEEPALIVE_INTERVAL=1200
```

## 📊 日志说明

日志保存在 `logs/` 目录，支持不同级别：

- **INFO** - 显示关键操作和仓位变动
- **DEBUG** - 显示详细的 WebSocket 数据和内部处理流程

## 🔧 功能详解

### 消息聚合机制

将同一交易对在短时间窗口内的多次变动聚合为一条消息，防止重复推送。

### Telegram Topic ID 支持

支持发送到群组中的话题组：

```env
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_TOPIC_ID=30
```

### 多账户支持

可以同时监控：
- 标准合约账户（USDT-M 合约）
- 统一账户（Portfolio Margin）

## 📝 许可证

MIT License