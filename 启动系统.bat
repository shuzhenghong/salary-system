@echo off
chcp 65001 >nul
title 人员薪酬管理系统
echo ========================================
echo   人员薪酬管理系统 - 局域网版
echo ========================================
echo.
echo   本机访问: http://127.0.0.1:5050
echo   局域网访问: http://本机IP:5050
echo   默认账号: admin / admin123
echo.
echo   按 Ctrl+C 可停止服务
echo ========================================
echo.

cd /d "%~dp0dist"
"人员薪酬管理系统.exe"
pause