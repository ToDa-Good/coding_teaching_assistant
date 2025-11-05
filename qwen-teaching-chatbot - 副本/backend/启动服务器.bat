@echo off
chcp 65001
echo ========================================
echo 启动编程教学助手后端服务器
echo ========================================
echo.
echo 检查.env配置文件...
if not exist .env (
    echo [错误] 缺少.env配置文件
    echo 请创建.env文件并配置API密钥
    pause
    exit /b 1
)
echo [OK] .env文件存在
echo.
echo 检查优化提示词...
if exist ..\results\system_prompt_*.txt (
    echo [OK] 找到优化提示词文件
) else (
    echo [警告] 未找到优化提示词，将使用默认提示词
)
echo.
echo 启动服务器...
echo ========================================
node server_optimized.js

