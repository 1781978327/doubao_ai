@echo off
echo 开始打包截图上传客户端...
pyinstaller -F --noconsole --name "系统助手" ^
  --hidden-import "pyautogui" ^
  --hidden-import "pystray" ^
  --hidden-import "PIL" ^
  send_picture.py
echo 打包完成！可执行文件在 dist 目录下
pause