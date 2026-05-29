@echo off
chcp 65001 >nul
cd /d "d:\1共享文件夹备份\编外人员"
echo ========================================
echo   人员薪酬管理系统 - 启动中...
echo ========================================
"C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe" app.py
pause