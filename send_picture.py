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
from PIL import Image, ImageDraw, ImageFont
import pystray
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
        self.tray_icon = None

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

            filename_bytes = filename.encode("utf-8")
            filename_len = struct.pack("!I", len(filename_bytes))
            client_socket.sendall(filename_len)
            client_socket.sendall(filename_bytes)

            with open(file_path, "rb") as f:
                file_data = f.read()
            file_len = struct.pack("!I", len(file_data))
            client_socket.sendall(file_len)

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
        screenshot_thread = threading.Thread(target=self._run_screenshot_thread, daemon=True)
        screenshot_thread.start()
        print(f"[主程序] 截图线程已启动（间隔{self.screenshot_interval}秒）")

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
        self.is_running = False
        if self.tray_icon:
            self.tray_icon.stop()


class ConfigWindow:
    """配置窗口：包含IP、端口、截图间隔输入框"""
    def __init__(self, root):
        self.root = root
        self.root.title("截图上传客户端 - 配置")
        self.root.geometry("450x300")  # 大幅增大窗口尺寸
        self.root.resizable(False, False)

        # 居中显示
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        # 主框架，设置大的内边距
        main_frame = ttk.Frame(self.root, padding=30)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. IP输入框
        ttk.Label(main_frame, text="服务器IP地址：").grid(row=0, column=0, sticky=tk.W, pady=(10, 10))
        self.ip_entry = ttk.Entry(main_frame, width=35)
        self.ip_entry.grid(row=0, column=1, pady=(10, 10))
        self.ip_entry.insert(0, "192.168.1.6")  # 默认IP

        # 2. 端口输入框
        ttk.Label(main_frame, text="服务器端口：").grid(row=1, column=0, sticky=tk.W, pady=(10, 10))
        self.port_entry = ttk.Entry(main_frame, width=35)
        self.port_entry.grid(row=1, column=1, pady=(10, 10))
        self.port_entry.insert(0, "7893")  # 默认端口

        # 3. 截图间隔输入框
        ttk.Label(main_frame, text="截图间隔（秒）：").grid(row=2, column=0, sticky=tk.W, pady=(10, 10))
        self.interval_entry = ttk.Entry(main_frame, width=35)
        self.interval_entry.grid(row=2, column=1, pady=(10, 30))
        self.interval_entry.insert(0, "60")  # 默认间隔

        # 按钮区域，设置更大的垂直间距
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="确定", command=self.start_client).grid(row=0, column=0, padx=20)
        ttk.Button(btn_frame, text="取消", command=root.quit).grid(row=0, column=1, padx=20)

    def validate_inputs(self):
        """验证IP、端口、间隔的有效性"""
        # 验证IP
        ip = self.ip_entry.get().strip()
        parts = ip.split('.')
        if len(parts) != 4:
            return False, "IP地址格式错误（需为xxx.xxx.xxx.xxx）"
        for part in parts:
            if not part.isdigit() or not (0 <= int(part) <= 255):
                return False, "IP地址格式错误（每个段需为0-255的数字）"
        
        # 验证端口（1-65535之间的整数）
        try:
            port = int(self.port_entry.get().strip())
            if not (1 <= port <= 65535):
                return False, "端口号需为1-65535之间的整数"
        except ValueError:
            return False, "端口号需为整数"
        
        # 验证截图间隔（正整数）
        try:
            interval = int(self.interval_entry.get().strip())
            if interval <= 0:
                return False, "截图间隔需为正整数"
        except ValueError:
            return False, "截图间隔需为整数"
        
        return True, "验证通过"

    def start_client(self):
        """验证输入并启动客户端"""
        valid, msg = self.validate_inputs()
        if not valid:
            messagebox.showerror("输入错误", msg)
            return

        server_ip = self.ip_entry.get().strip()
        server_port = int(self.port_entry.get().strip())
        screenshot_interval = int(self.interval_entry.get().strip())

        self.root.destroy()
        self.start_tray_and_service(server_ip, server_port, screenshot_interval)

    def start_tray_and_service(self, server_ip, server_port, screenshot_interval):
        """启动托盘和后台服务（传入端口和间隔参数）"""
        client = SocketClient(
            server_ip=server_ip,
            server_port=server_port,
            screenshot_interval=screenshot_interval,
            screenshot_dir="screenshots"
        )

        service_thread = threading.Thread(target=client.run_all, daemon=True)
        service_thread.start()

        def on_quit(icon, item):
            client.stop()
            icon.stop()
            sys.exit(0)

        icon_image = Image.new('RGB', (64, 64), color='#2E86AB')
        draw = ImageDraw.Draw(icon_image)
        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except:
            font = ImageFont.load_default(size=32)
        draw.text((18, 10), "截", fill="white", font=font)

        tray_icon = pystray.Icon(
            name="screenshot_uploader",
            icon=icon_image,
            title=f"截图上传客户端（{server_ip}:{server_port}）"
        )
        tray_icon.menu = pystray.Menu(pystray.MenuItem("退出", on_quit))
        client.tray_icon = tray_icon

        tray_icon.notify(
            f"已连接到 {server_ip}:{server_port}\n截图间隔：{screenshot_interval}秒", 
            "启动成功"
        )
        tray_icon.run()


if __name__ == "__main__":
    root = tk.Tk()
    app = ConfigWindow(root)
    root.mainloop()