# socket_client_with_screenshot.py
import os
import time
import socket
import struct
import glob
import threading
from typing import Optional, List
from datetime import datetime
from screenshot_core import ScreenshotCore  # 导入截图模块

class SocketClient:
    def __init__(self, server_ip: str, server_port: int = 7893, 
                 screenshot_dir: str = "screenshots", screenshot_interval: int = 60):
        """
        集成截图+传图的客户端类
        :param server_ip: 服务端IP（必填）
        :param server_port: 服务端端口（默认8888）
        :param screenshot_dir: 截图保存目录（需与ScreenshotCore一致）
        :param screenshot_interval: 截图间隔（秒，默认60）
        """
        self.server_ip = server_ip
        self.server_port = server_port
        self.screenshot_dir = screenshot_dir
        self.screenshot_interval = screenshot_interval
        self.sent_files = set()  # 记录已发送文件，避免重复
        self.is_running = True   # 控制循环运行的标志

        # 初始化截图模块（关联同一个保存目录）
        self.screenshot_core = ScreenshotCore(
            save_dir=self.screenshot_dir,
            interval=self.screenshot_interval
        )

    def _get_latest_screenshots(self, max_age: int = 300) -> List[str]:
        """获取截图目录中未发送的新文件（5分钟内）"""
        if not os.path.exists(self.screenshot_dir):
            print(f"[传图模块] 截图目录不存在：{self.screenshot_dir}")
            return []

        png_files = glob.glob(os.path.join(self.screenshot_dir, "screenshot_*.png"))
        new_files = []
        for file in png_files:
            filename = os.path.basename(file)
            if filename in self.sent_files:
                continue
            
            # 过滤旧文件
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file))
            if (datetime.now() - file_mtime).total_seconds() > max_age:
                print(f"[传图模块] 跳过旧文件：{file}")
                self.sent_files.add(filename)
                continue
            
            new_files.append(file)
        
        # 按时间排序（确保按截图顺序发送）
        new_files.sort(key=lambda x: os.path.getmtime(x))
        return new_files

    def send_single_file(self, file_path: str) -> bool:
        """发送单个文件到服务端"""
        if not os.path.exists(file_path):
            print(f"[传图模块] 待发送文件不存在：{file_path}")
            return False

        filename = os.path.basename(file_path)
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(15)
            client_socket.connect((self.server_ip, self.server_port))
            print(f"\n[传图模块] 已连接服务端：{self.server_ip}:{self.server_port}")

            # 1. 发送文件名（先传长度，避免粘包）
            filename_bytes = filename.encode("utf-8")
            filename_len = struct.pack("!I", len(filename_bytes))
            client_socket.sendall(filename_len)
            client_socket.sendall(filename_bytes)

            # 2. 发送文件数据
            with open(file_path, "rb") as f:
                file_data = f.read()
            file_len = struct.pack("!I", len(file_data))
            client_socket.sendall(file_len)

            # 分块发送（1MB/次）
            sent_bytes = 0
            total_bytes = len(file_data)
            while sent_bytes < total_bytes and self.is_running:
                chunk = file_data[sent_bytes:sent_bytes + 1024 * 1024]
                client_socket.sendall(chunk)
                sent_bytes += len(chunk)
                progress = (sent_bytes / total_bytes) * 100
                print(f"[传图模块] 发送进度：{progress:.1f}%", end="\r")

            if sent_bytes == total_bytes:
                self.sent_files.add(filename)
                print(f"\n[传图模块] 发送成功：{filename}（{total_bytes/1024:.1f}KB）")
                return True
            else:
                print(f"\n[传图模块] 发送中断：{filename}")
                return False

        except socket.timeout:
            print(f"\n[传图模块] 发送超时：{self.server_ip}:{self.server_port}")
            return False
        except ConnectionRefusedError:
            print(f"\n[传图模块] 服务端拒绝连接：请确认服务端已启动")
            return False
        except Exception as e:
            print(f"\n[传图模块] 发送失败：{str(e)}")
            return False
        finally:
            try:
                client_socket.close()
            except:
                pass

    def _run_screenshot_thread(self) -> None:
        """截图线程的执行函数（内部调用，不直接对外）"""
        self.screenshot_core.run_loop()

    def run_all(self, check_interval: int = 10) -> None:
        """启动所有功能：截图线程 + 传图监控"""
        # 1. 启动截图线程（独立线程，不阻塞传图逻辑）
        screenshot_thread = threading.Thread(
            target=self._run_screenshot_thread,
            daemon=True  # 设为守护线程：主程序退出时自动结束
        )
        screenshot_thread.start()
        print(f"[主程序] 截图线程已启动（间隔{self.screenshot_interval}秒）")

        # 2. 启动传图监控（主线程执行）
        print(f"[主程序] 传图监控已启动（每{check_interval}秒检查一次）")
        print(f"[主程序] 目标服务端：{self.server_ip}:{self.server_port}，按Ctrl+C停止")

        try:
            while self.is_running:
                new_files = self._get_latest_screenshots(max_age=300)
                if new_files:
                    print(f"[主程序] 发现{len(new_files)}个未发送截图，开始发送...")
                    for file in new_files:
                        if not self.is_running:
                            break
                        self.send_single_file(file)
                else:
                    # 无新文件时，简洁提示（避免刷屏）
                    print(f"[主程序] 无新截图（{datetime.now().strftime('%H:%M:%S')}）", end="\r")
                
                # 控制检查间隔（同时响应退出信号）
                for _ in range(check_interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n[主程序] 收到停止信号，正在关闭...")
            self.is_running = False
        finally:
            print("[主程序] 所有功能已停止")

# 单文件运行入口（只需运行这个文件）
if __name__ == "__main__":
    # -------------------------- 关键配置（必须修改！） --------------------------
    SERVER_IP = "192.168.1.6"  # 替换为你的服务端IP（如192.168.0.5）
    SCREENSHOT_INTERVAL = 60     # 截图间隔（秒，默认60秒/次）
    SCREENSHOT_DIR = "screenshots"  # 截图保存目录（默认即可，无需修改）
    # --------------------------------------------------------------------------

    # 初始化并启动所有功能
    client = SocketClient(
        server_ip=SERVER_IP,
        screenshot_interval=SCREENSHOT_INTERVAL,
        screenshot_dir=SCREENSHOT_DIR
    )
    client.run_all(check_interval=10)  # 每10秒检查一次新截图