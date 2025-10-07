# 热重载使用说明

## 功能说明
热重载脚本允许您在不影响正在监控的订单的情况下更新代码。程序会优雅地停止当前实例并启动新实例，确保监控的连续性。

## 使用方法

### 1. 查看程序状态
```bash
python hot_reload.py status
```

### 2. 热重载程序（推荐）
```bash
python hot_reload.py reload
```
这会发送重启信号给当前程序，程序会优雅地停止并重新启动。

### 3. 更新代码并热重载
```bash
python hot_reload.py update
```
这会先执行 `git pull` 拉取最新代码，然后热重载程序。

### 4. 停止程序
```bash
python hot_reload.py stop
```

### 5. 启动程序
```bash
python hot_reload.py start
```

## 工作原理

1. **信号处理**: 程序监听 `SIGUSR1` 信号，收到信号后会优雅地停止当前实例
2. **进程替换**: 使用 `os.execv()` 替换当前进程，启动新实例
3. **状态保持**: 重启过程中会保持WebSocket连接和监控状态
4. **无缝切换**: 新实例会立即接管监控任务

## 注意事项

- 热重载过程中会有短暂的重连时间（通常1-3秒）
- 确保代码更新后程序能正常启动
- 如果热重载失败，可以手动重启程序
- PID文件 `.monitor.pid` 用于跟踪程序状态

## 示例场景

### 场景1: 代码更新后热重载
```bash
# 1. 推送代码到git
git add .
git commit -m "修复bug"
git push origin main

# 2. 在服务器上热重载
python hot_reload.py update
```

### 场景2: 配置修改后热重载
```bash
# 修改配置文件后
python hot_reload.py reload
```

### 场景3: 检查程序状态
```bash
python hot_reload.py status
```
