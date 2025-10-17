import pyautogui
import time
from datetime import datetime
import os

def auto_screenshot(interval=60):
    """
    定时截取屏幕并保存图片
    
    参数:
        interval: 截图时间间隔(秒)，默认60秒
    """
    # 创建保存截图的文件夹
    save_dir = "screenshots"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    print(f"开始自动截图，每{interval}秒一次，按Ctrl+C停止")
    
    try:
        while True:
            # 获取当前时间作为文件名
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{save_dir}/screenshot_{current_time}.png"
            
            # 截取屏幕并保存
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            print(f"已保存截图: {filename}")
            
            # 等待指定时间
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n程序已停止")

if __name__ == "__main__":
    auto_screenshot(60)  # 每60秒截图一次