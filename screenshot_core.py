# screenshot_core.py
import pyautogui
import time
import os
from datetime import datetime
from typing import Optional

class ScreenshotCore:
    def __init__(self, save_dir: str = "screenshots", interval: int = 60):
        """截图核心类：仅负责定时截图+本地保存"""
        self.save_dir = save_dir
        self.interval = interval
        self._init_save_dir()

    def _init_save_dir(self) -> None:
        """初始化截图保存目录"""
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            print(f"[截图模块] 已创建保存目录：{os.path.abspath(self.save_dir)}")
        else:
            print(f"[截图模块] 已存在保存目录：{os.path.abspath(self.save_dir)}")

    def take_screenshot(self) -> Optional[str]:
        """执行单次截图并返回文件路径"""
        try:
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{time_str}.png"
            file_path = os.path.join(self.save_dir, filename)
            
            screenshot = pyautogui.screenshot()
            screenshot.save(file_path)
            print(f"[截图模块] 已保存截图：{file_path}")
            return file_path
        except Exception as e:
            print(f"[截图模块] 截图失败：{str(e)}")
            return None

    def run_loop(self) -> None:
        """启动定时截图循环（阻塞函数，需在独立线程中运行）"""
        print(f"[截图模块] 开始定时截图（间隔{self.interval}秒），按Ctrl+C停止")
        try:
            while True:
                self.take_screenshot()
                time.sleep(self.interval)
        except KeyboardInterrupt:
            print("\n[截图模块] 定时截图循环已停止")