import os
import time
import socket
import struct
import glob
import threading
import sys
from typing import Optional, List
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageDraw, ImageFont  # 需安装Pillow：pip install pillow
import pystray  # 需安装系统托盘库：pip install pystray
from screenshot_core import ScreenshotCore

class SocketClient:
    def __init__(self, server_ip: str, server_port: int = 7893, 
                 screenshot_dir: str = "screenshots", screenshot_interval: int = 60):
        self.server_ip = server_ip
        self.server_port = server_port
        self.screenshot_dir = screenshot_dir
        self.screenshot_interval = screenshot_interval
        self.sent_files = set()
        self.is_running = True
        self.screenshot_core = ScreenshotCore(save_dir=screenshot_dir, interval=screenshot_interval)
        self.tray_icon = None  # 托盘图标对象

    def _get_latest_screenshots(self, max_age: int = 300) -> List[str]:
        if not os.path.exists(self.screenshot_dir):
            print(f"[传图模块] 截图目录不存在：{self.screenshot_dir}")
            return []

        png_files = glob.glob(os.path.join(self.screenshot_dir, "screenshot_*.png"))
        new_files = []
        for file in png_files:
            filename = os.path.basename(file)
            if filename in self.sent_files:
                continue
            
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file))
            if (datetime.now() - file_mtime).total_seconds() > max_age:
                print(f"[传图模块] 跳过旧文件：{file}")
                self.sent_files.add(filename)
                continue
            
            new_files.append(file)
        
        new_files.sort(key=lambda x: os.path.getmtime(x))
        return new_files

    def send_single_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            print(f"[传图模块] 待发送文件不存在：{file_path}")
            return False

        filename = os.path.basename(file_path)
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(15)
            client_socket.connect((self.server_ip, self.server_port))
            print(f"\n[传图模块] 已连接服务端：{self.server_ip}:{self.server_port}")

            # 发送文件名
            filename_bytes = filename.encode("utf-8")
            filename_len = struct.pack("!I", len(filename_bytes))
            client_socket.sendall(filename_len)
            client_socket.sendall(filename_bytes)

            # 发送文件数据
            with open(file_path, "rb") as f:
                file_data = f.read()
            file_len = struct.pack("!I", len(file_data))
            client_socket.sendall(file_len)

            # 分块发送
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

        except Exception as e:
            print(f"\n[传图模块] 发送失败：{str(e)}")
            return False
        finally:
            try:
                client_socket.close()
            except:
                pass

    def _run_screenshot_thread(self) -> None:
        self.screenshot_core.run_loop()

    def run_all(self, check_interval: int = 10) -> None:
        # 启动截图线程
        screenshot_thread = threading.Thread(target=self._run_screenshot_thread, daemon=True)
        screenshot_thread.start()
        print(f"[主程序] 截图线程已启动（间隔{self.screenshot_interval}秒）")

        # 启动传图监控
        print(f"[主程序] 目标服务端：{self.server_ip}:{self.server_port}")
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
                    print(f"[主程序] 无新截图（{datetime.now().strftime('%H:%M:%S')}）", end="\r")
                
                for _ in range(check_interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n[主程序] 收到停止信号")
        finally:
            self.is_running = False
            print("[主程序] 所有功能已停止")

    def stop(self):
        """停止所有线程"""
        self.is_running = False
        if self.tray_icon:
            self.tray_icon.stop()


class IPToolWindow:
    """IP输入窗口"""
    def __init__(self, root):
        self.root = root
        self.root.title("截图上传客户端")
        self.root.geometry("300x150")
        self.root.resizable(False, False)
        self.root.iconbitmap(default="")  # 可自定义图标

        # 居中显示
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        # 界面元素
        ttk.Label(self.root, text="请输入服务器IP地址：").pack(pady=10)
        self.ip_entry = ttk.Entry(self.root, width=20)
        self.ip_entry.pack(pady=5)
        self.ip_entry.insert(0, "192.168.1.6")  # 默认IP

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确定", command=self.start_client).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=root.quit).pack(side=tk.LEFT, padx=5)

    def validate_ip(self, ip):
        """简单验证IP格式"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit() or not (0 <= int(part) <= 255):
                return False
        return True

    def start_client(self):
        """验证IP并启动客户端"""
        server_ip = self.ip_entry.get().strip()
        if not self.validate_ip(server_ip):
            messagebox.showerror("错误", "请输入有效的IP地址（如192.168.1.6）")
            return

        # 关闭输入窗口，启动后台服务和托盘
        self.root.destroy()
        self.start_tray_and_service(server_ip)

    def start_tray_and_service(self, server_ip):
        """启动系统托盘和后台服务（修复图标创建错误）"""
        # 初始化客户端
        client = SocketClient(
            server_ip=server_ip,
            screenshot_interval=60,
            screenshot_dir="screenshots"
        )

        # 启动后台服务线程
        service_thread = threading.Thread(target=client.run_all, daemon=True)
        service_thread.start()

        # 创建托盘图标（修复：用纯PIL图片，不依赖Tkinter）
        def on_quit(icon, item):
            client.stop()
            icon.stop()
            sys.exit(0)

        # 1. 生成纯PIL格式的图标（蓝色背景，64x64大小）
        icon_image = Image.new('RGB', (64, 64), color='#2E86AB')  # 蓝色背景
        # 在图标上添加文字“截”，更直观
        draw = ImageDraw.Draw(icon_image)
        try:
            # 尝试加载系统默认字体
            font = ImageFont.truetype("arial.ttf", 32)
        except:
            # 没有arial字体时用默认字体
            font = ImageFont.load_default(size=32)
        # 在图标中心画文字
        draw.text((18, 10), "截", fill="white", font=font)

        # 2. 创建托盘图标（直接用PIL的Image对象，不依赖Tkinter）
        tray_icon = pystray.Icon(
            name="screenshot_uploader",
            icon=icon_image,  # 直接传PIL图片
            title="截图上传客户端"
        )
        # 设置右键菜单
        tray_icon.menu = pystray.Menu(pystray.MenuItem("退出", on_quit))
        client.tray_icon = tray_icon

        # 显示托盘提示并运行托盘
        tray_icon.notify("截图上传客户端已启动", "提示")
        tray_icon.run()


if __name__ == "__main__":
    # 启动IP输入窗口
    root = tk.Tk()
    app = IPToolWindow(root)
    root.mainloop()