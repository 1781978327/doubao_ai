@echo off
echo 开始打包...
pyinstaller -F --name "截图上传客户端" --hidden-import "pyautogui" --hidden-import "pystray" --hidden-import "PIL" send_picture.py
echo 打包完成！EXE在dist目录下
pause