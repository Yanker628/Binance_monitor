# 币安合约监控机器人 🤖

一个功能完整、稳定可靠的币安合约监控系统，实时监控仓位变动，并通过 Telegram Bot 推送通知。

## ✨ 核心特性

### 🎯 实时监控
- ✅ **开仓检测** - 实时捕获新开仓位
- ✅ **平仓检测** - 及时通知平仓及盈亏
- ✅ **加仓/减仓** - 追踪仓位变化
- 📊 **智能聚合** - 多次快速操作自动合并为一条消息
- 🔄 **WebSocket 实时** - 低延迟，秒级响应

### 💪 稳定可靠
- 🔐 **双账户支持** - 同时监控标准合约账户和统一账户
- 🔄 **自动重连** - WebSocket 断线自动重连
- ⏰ **listenKey 续期** - 自动保持连接活跃
- 🛡️ **异常处理** - 完善的错误捕获和日志记录
- 🔧 **后台事件循环** - 异步处理，不阻塞主线程

### 📱 消息推送
- 🚀 **开仓通知** - 显示币种、方向、数量、价格、USDT 价值
- ✅ **平仓通知** - 显示实际盈亏（不是 0）
- ➕ **加仓通知** - 显示仓位从 X → Y USDT
- ➖ **减仓通知** - 显示减少百分比和剩余仓位
- 📊 **聚合功能** - 多次变动合并为一条消息（后台日志记录详情）

### 🎨 消息格式
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

## 📁 项目结构

```
binance_monitor/
├── config/              # 配置管理
│   ├── __init__.py
│   └── settings.py      # 配置类（支持环境变量）
├── binance/            # 币安API模块
│   ├── __init__.py
│   ├── auth.py         # 认证工具（签名生成）
│   ├── client.py       # REST API客户端
│   └── ws_client.py    # WebSocket客户端（支持重连）
├── monitor/            # 监控模块
│   ├── __init__.py
│   └── position_monitor.py  # 仓位监控器（追踪变化）
├── notifier/           # Telegram通知模块
│   ├── __init__.py
│   ├── bot.py          # Bot封装（同步发送）
│   └── aggregator.py   # 消息聚合器（智能合并）
├── utils/              # 工具模块
│   ├── __init__.py
│   ├── formatter.py    # 消息格式化（统一格式）
│   └── logger.py       # 日志配置（支持DEBUG模式）
├── logs/               # 日志目录（自动创建）
├── main.py             # 主程序入口
├── requirements.txt    # 依赖包
├── .env.example        # 环境变量示例
├── .env                # 环境变量配置（需自行创建）
├── .gitignore
└── README.md
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd binance_monitor
```

### 2. 安装依赖

推荐使用虚拟环境：

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

复制示例文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置：

```env
# ============================================
# Telegram Bot 配置（支持多Bot推送）
# ============================================
# 主 Bot（必填）
TELEGRAM_BOT_TOKEN=你的bot_token
TELEGRAM_CHAT_ID=你的chat_id  # 可以是群组ID（负数）
TELEGRAM_TOPIC_ID=30  # 可选，话题ID（用于群组中的话题组）

# 第二个 Bot（可选，用于同时推送到多个地方）
TELEGRAM_BOT_TOKEN_2=你的第二个bot_token  # 不填则只使用主Bot
TELEGRAM_CHAT_ID_2=你的第二个chat_id
TELEGRAM_TOPIC_ID_2=  # 可选，第二个Bot的话题ID

# ============================================
# 币安标准合约账户配置（可选）
# ============================================
BINANCE_FUTURES_ENABLED=True  # 是否启用
BINANCE_API_KEY=你的API_KEY
BINANCE_API_SECRET=你的API_SECRET

# ============================================
# 币安统一账户配置（可选）
# ============================================
BINANCE_UNIFIED_ENABLED=False  # 是否启用
BINANCE_UNIFIED_API_KEY=你的统一账户API_KEY
BINANCE_UNIFIED_API_SECRET=你的统一账户API_SECRET

# ============================================
# 其他配置
# ============================================
BINANCE_TESTNET=False  # True使用测试网，False使用主网
MESSAGE_AGGREGATION_WINDOW_MS=1000  # 消息聚合窗口（毫秒）
```

**⚠️ 重要提示：**
- 至少需要启用一个账户（标准合约或统一账户）
- API Key 需要开启合约权限和 WebSocket 权限
- 建议只开启读取权限，不需要交易权限
- 不要将 `.env` 文件提交到 Git

### 4. 获取 Telegram Bot Token 和 Chat ID

#### 4.1 创建 Bot
1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 创建新 bot
3. 按提示设置 bot 名称
4. 获取 Bot Token（格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

#### 4.2 获取 Chat ID
**方法1：私聊（推荐用于个人）**
1. 向你的 bot 发送任意消息
2. 浏览器访问：`https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates`
3. 在返回的 JSON 中找到 `"chat":{"id": 123456789}`

**方法2：群组（推荐用于团队）**
1. 将 bot 添加到群组
2. 在群组中发送任意消息（提到 bot）
3. 访问上述 URL
4. 找到 `"chat":{"id": -1001234567890}` （群组 ID 是负数）

### 5. 运行程序

```bash
python3 main.py
```

**启动成功后会看到：**
```
2025-10-05 22:13:30 - binance_monitor - INFO - 🚀 币安合约监控启动
2025-10-05 22:13:30 - binance_monitor - INFO - ✅ 后台事件循环已启动
2025-10-05 22:13:30 - binance_monitor - INFO - 📱 Telegram Bot 已初始化，Chat ID: -1001234567890, Topic ID: 30
2025-10-05 22:13:30 - binance_monitor - INFO - ✅ Bot #1 已注册 (Topic: 30)
2025-10-05 22:13:30 - binance_monitor - INFO - 📱 多 Bot 管理器已初始化，共 1 个 Bot
2025-10-05 22:13:30 - binance_monitor - INFO - ✅ [合约账户] WebSocket 连接成功
2025-10-05 22:13:30 - binance_monitor - INFO - ✅ 监控已启动
```

## 📊 日志说明

### 日志位置
所有日志保存在 `logs/` 目录：
```
logs/binance_monitor_20251005.log
```

### 日志级别

**INFO 模式（默认）**
```bash
python3 main.py
```
显示关键操作和仓位变动

**DEBUG 模式（调试）**
```bash
export BINANCE_LOG_LEVEL=DEBUG
python3 main.py
```
显示详细的 WebSocket 数据和内部处理流程

### 日志示例

**开仓日志：**
```
[合约账户] ✅ 开仓 BTCUSDT LONG 0.1000币 @ 40000.0000 = 4000.00 USDT
[聚合] 📥 接收到仓位变动: BTCUSDT OPEN
[聚合] 创建新缓冲区: BTCUSDT_BOTH
[聚合] 准备推送聚合消息，包含 1 条仓位变动
[Telegram] ✅ 消息发送成功
```

**平仓日志：**
```
[合约账户] ❌ 平仓 BTCUSDT LONG 盈亏: +50.00 USDT
[聚合] 📥 接收到仓位变动: BTCUSDT CLOSE
[Telegram] ✅ 消息发送成功
```

**聚合日志：**
```
[聚合] 📥 接收到仓位变动: ETHUSDT ADD
[聚合] 更新缓冲区: ETHUSDT_BOTH, 类型: ADD, 次数: 5
[聚合] ETHUSDT 聚合了 5 次变动  # 只在日志中记录，Telegram不显示
```

**多 Bot 推送日志：**
```
[多Bot] ✅ 消息发送完成: 成功 2/2
[Telegram] ✅ 消息发送成功 (Topic: 30)
[Telegram] ✅ 消息发送成功
```

## 🔧 功能详解

### Telegram Topic ID 支持

**什么是 Topic ID？**
- Topic ID 是 Telegram 群组中话题组（话题）的标识符
- 用于在群组中创建不同的讨论话题
- 消息会发送到指定的话题中，而不是群组的主聊天

**如何获取 Topic ID？**
1. 在群组中创建话题组
2. 向话题组发送消息
3. 访问：`https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates`
4. 在返回的 JSON 中找到 `"message_thread_id": 30`

**配置示例：**
```env
# 发送到群组的主聊天
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_TOPIC_ID=  # 留空或不设置

# 发送到群组的话题组
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_TOPIC_ID=30  # 话题ID
```

**注意事项：**
- Topic ID 只在群组中有效
- 私聊不需要设置 Topic ID
- 如果设置了错误的 Topic ID，消息会发送到群组主聊天

### 消息聚合机制

**问题：** 币安订单可能分批成交，一个 200 USDT 的订单可能产生 5-10 次 WebSocket 事件

**解决：** 智能聚合器
- 1000ms 聚合窗口
- 同一交易对的多次变动自动合并
- Telegram 只收到 1 条消息显示最终结果
- 后台日志记录所有详细变动

**示例：**
```
# WebSocket 收到（5次事件）
开仓 20 USDT
加仓 +30 USDT
加仓 +50 USDT
加仓 +60 USDT
加仓 +40 USDT

# Telegram 收到（1条消息）
🚀 开仓成功
• 当前仓位: 200.00 USDT  # 最终结果
```

### 双账户支持

支持同时监控两种账户类型：

1. **标准合约账户** - USDT-M 合约
2. **统一账户** - Portfolio Margin

可以同时启用或只启用其中一个。

### 方向显示修复

**问题：** 平仓时 position_amt = 0，无法判断原来的方向

**解决：** 
- 平仓前保存方向（LONG/SHORT）
- 显示时使用保存的方向
- 确保"做多平仓"显示"做多"，不会显示"做空"

### WebSocket 事件过滤

**已知可忽略的事件：**
- `TRADE_LITE` - 交易简报（轻量级），无需处理
- `listenKeyExpired` - listenKey 过期提醒（已自动续期）

这些事件不会产生警告日志，保持日志清洁。

## 🔍 故障排查

### 问题1：Telegram 没有收到消息

**检查步骤：**

1. **验证配置**
```bash
# 查看日志
tail -f logs/binance_monitor_*.log

# 应该看到
✅ 后台事件循环已启动
📱 Telegram Bot 已初始化
✅ 监控已启动
```

2. **检查聚合器日志**
```bash
# 应该看到
[聚合] 📥 接收到仓位变动
[聚合] 准备推送聚合消息
[Telegram] ✅ 消息发送成功
```

3. **测试 Telegram 连接**
```python
# 创建 test_telegram.py
from config import Settings
from notifier import TelegramBot

Settings.validate()
bot = TelegramBot(Settings.TELEGRAM_BOT_TOKEN, Settings.TELEGRAM_CHAT_ID)
bot.send_message_sync("测试消息")
```

**常见原因：**
- ❌ Bot Token 或 Chat ID 错误
- ❌ Bot 未加入群组
- ❌ 网络问题

### 问题2：WebSocket 频繁断开

**解决方案：**
- 程序已实现自动重连
- listenKey 自动续期（每30分钟）
- 检查网络稳定性

### 问题3：显示的仓位金额不对

**可能原因：**

1. **分批成交** - 正常现象，等待聚合完成
2. **杠杆影响** - 显示的是仓位价值，不是保证金
3. **价格波动** - 使用 mark price 计算，实时变化

**验证方法：**
```bash
# 查看详细日志
export BINANCE_LOG_LEVEL=DEBUG
python3 main.py

# 会显示
📦 原始数据 BTCUSDT: pa=0.1, ep=40000, up=50
```

### 问题4：平仓方向显示错误

✅ **已修复** - 现在会正确显示平仓前的方向

**示例：**
```
✅ 平仓完成
• 方向: 做多  ← 正确显示做多，不会显示做空
```

## 🔐 安全建议

1. **API 权限**
   - ✅ 只开启读取权限

2. **API Key 保护**
   - 将 `.env` 添加到 `.gitignore`
   - 不要将 API Key 提交到代码仓库
   - 定期更换 API Key

3. **服务器安全**
   - 使用防火墙限制入站连接
   - 定期更新系统和依赖包
   - 监控异常活动

## 📈 性能优化

### 资源占用
- **CPU**: < 5% (闲时)
- **内存**: ~50MB
- **网络**: WebSocket 保持连接，流量极小

### 延迟
- WebSocket 推送：< 100ms
- 聚合延迟：1000ms（可配置）
- Telegram 发送：~200-500ms

## 🛠️ 高级配置

### 修改聚合窗口

编辑 `main.py`:
```python
self.aggregator = MessageAggregator(
    send_callback=self.telegram.send_message_sync,
    window_ms=1000  # 修改这个值（毫秒）
)
```

### 修改日志级别

```bash
# 临时设置
export BINANCE_LOG_LEVEL=DEBUG

# 或在代码中修改 main.py
logger = setup_logger('binance_monitor', logging.DEBUG)
```

### 添加自定义通知

编辑 `utils/formatter.py` 中的消息格式函数：
```python
def format_open_position_message(position) -> str:
    # 自定义消息格式
    message = f"🚀 开仓成功\n..."
    return message
```

## 🐛 已知问题

### 已解决 ✅
- ✅ Telegram 推送失败 - 已添加后台事件循环
- ✅ 消息聚合不工作 - 已修复 logger 配置
- ✅ 平仓方向显示错误 - 已保存平仓前方向
- ✅ WebSocket 事件警告 - 已添加忽略列表

### 待优化 📝
- 暂无

## 📄 依赖包

```txt
requests>=2.31.0      # HTTP 请求
websocket-client>=1.6.0  # WebSocket 客户端
python-dotenv>=1.0.0     # 环境变量管理
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📜 许可证

MIT License

## 📞 联系方式
+86 18145646579

如有问题，请提交 Issue 或联系维护者。

---

**⚠️ 免责声明**

本软件仅用于个人监控和通知，不提供交易建议。使用本软件产生的任何盈亏由使用者自行承担。请合理使用杠杆，注意风险控制。
