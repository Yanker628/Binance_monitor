#!/usr/bin/env python3
"""
热重载脚本 - 支持不停机更新币安监控程序
使用方法：
    python hot_reload.py reload    # 重启程序
    python hot_reload.py stop      # 停止程序
    python hot_reload.py status    # 查看程序状态
"""

import os
import sys
import time
import signal
import subprocess
import psutil
from pathlib import Path

class HotReloadManager:
    def __init__(self):
        self.project_dir = Path(__file__).parent
        self.main_script = self.project_dir / "main.py"
        self.pid_file = self.project_dir / ".monitor.pid"
        
    def find_monitor_process(self):
        """查找正在运行的监控进程"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline:
                    # 检查命令行中是否包含main.py
                    cmdline_str = ' '.join(cmdline)
                    if 'main.py' in cmdline_str and 'binance_monitor' in cmdline_str:
                        return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def get_pid(self):
        """获取进程ID"""
        if self.pid_file.exists():
            try:
                return int(self.pid_file.read_text().strip())
            except (ValueError, FileNotFoundError):
                pass
        
        # 如果PID文件不存在或无效，尝试查找进程
        proc = self.find_monitor_process()
        return proc.pid if proc else None
    
    def save_pid(self, pid):
        """保存进程ID到文件"""
        self.pid_file.write_text(str(pid))
    
    def remove_pid_file(self):
        """删除PID文件"""
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def is_running(self):
        """检查程序是否正在运行"""
        pid = self.get_pid()
        if not pid:
            return False
        
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
    
    def start(self):
        """启动监控程序"""
        if self.is_running():
            print("❌ 监控程序已经在运行中")
            return False
        
        print("🚀 启动币安监控程序...")
        try:
            # 启动程序
            process = subprocess.Popen([
                sys.executable, str(self.main_script)
            ], cwd=str(self.project_dir))
            
            # 保存PID
            self.save_pid(process.pid)
            
            # 等待一下确保程序启动
            time.sleep(2)
            
            if self.is_running():
                print(f"✅ 监控程序已启动 (PID: {process.pid})")
                return True
            else:
                print("❌ 监控程序启动失败")
                return False
                
        except Exception as e:
            print(f"❌ 启动失败: {e}")
            return False
    
    def reload(self):
        """热重载程序"""
        if not self.is_running():
            print("❌ 监控程序未运行，无法重载")
            return False
        
        pid = self.get_pid()
        print(f"🔄 正在热重载监控程序 (PID: {pid})...")
        
        try:
            # 发送SIGUSR1信号触发优雅重启
            os.kill(pid, signal.SIGUSR1)
            
            # 等待重启完成
            print("⏳ 等待程序重启...")
            time.sleep(3)
            
            # 检查新进程是否启动
            if self.is_running():
                new_pid = self.get_pid()
                print(f"✅ 热重载成功！新进程PID: {new_pid}")
                return True
            else:
                print("❌ 热重载失败，程序可能已停止")
                return False
                
        except ProcessLookupError:
            print("❌ 进程不存在，可能已经停止")
            self.remove_pid_file()
            return False
        except PermissionError:
            print("❌ 权限不足，无法发送信号")
            return False
        except Exception as e:
            print(f"❌ 热重载失败: {e}")
            return False
    
    def stop(self):
        """停止监控程序"""
        if not self.is_running():
            print("❌ 监控程序未运行")
            return False
        
        pid = self.get_pid()
        print(f"⛔ 正在停止监控程序 (PID: {pid})...")
        
        try:
            # 发送SIGTERM信号触发优雅停止
            os.kill(pid, signal.SIGTERM)
            
            # 等待程序停止
            print("⏳ 等待程序停止...")
            time.sleep(3)
            
            if not self.is_running():
                print("✅ 监控程序已停止")
                self.remove_pid_file()
                return True
            else:
                print("⚠️  程序未响应，尝试强制停止...")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
                if not self.is_running():
                    print("✅ 监控程序已强制停止")
                    self.remove_pid_file()
                    return True
                else:
                    print("❌ 无法停止程序")
                    return False
                    
        except ProcessLookupError:
            print("❌ 进程不存在，可能已经停止")
            self.remove_pid_file()
            return False
        except Exception as e:
            print(f"❌ 停止失败: {e}")
            return False
    
    def status(self):
        """查看程序状态"""
        if self.is_running():
            pid = self.get_pid()
            try:
                proc = psutil.Process(pid)
                create_time = proc.create_time()
                uptime = time.time() - create_time
                memory_info = proc.memory_info()
                
                print(f"✅ 监控程序正在运行")
                print(f"   PID: {pid}")
                print(f"   运行时间: {uptime:.0f}秒 ({uptime/60:.1f}分钟)")
                print(f"   内存使用: {memory_info.rss / 1024 / 1024:.1f} MB")
                print(f"   CPU使用率: {proc.cpu_percent():.1f}%")
                
                # 显示命令行参数
                cmdline = proc.cmdline()
                print(f"   命令行: {' '.join(cmdline)}")
                
            except psutil.NoSuchProcess:
                print("❌ 进程不存在")
                self.remove_pid_file()
        else:
            print("❌ 监控程序未运行")
    
    def update_and_reload(self):
        """更新代码并热重载"""
        print("📥 正在拉取最新代码...")
        try:
            # 拉取最新代码
            result = subprocess.run(
                ['git', 'pull', 'origin', 'main'],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✅ 代码更新成功")
                print(result.stdout)
                
                # 热重载程序
                return self.reload()
            else:
                print("❌ 代码更新失败")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"❌ 更新失败: {e}")
            return False


def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python hot_reload.py start     # 启动程序")
        print("  python hot_reload.py reload    # 热重载程序")
        print("  python hot_reload.py stop      # 停止程序")
        print("  python hot_reload.py status    # 查看状态")
        print("  python hot_reload.py update    # 更新代码并热重载")
        sys.exit(1)
    
    manager = HotReloadManager()
    command = sys.argv[1].lower()
    
    if command == 'start':
        manager.start()
    elif command == 'reload':
        manager.reload()
    elif command == 'stop':
        manager.stop()
    elif command == 'status':
        manager.status()
    elif command == 'update':
        manager.update_and_reload()
    else:
        print(f"❌ 未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
