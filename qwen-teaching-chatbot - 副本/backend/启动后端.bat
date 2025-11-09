@echo off
chcp 65001
cd /d "%~dp0"
echo ========================================
echo 启动编程教学助手后端服务器
echo ========================================
echo.
echo 当前目录: %CD%
echo.
node server_optimized.js
pause

