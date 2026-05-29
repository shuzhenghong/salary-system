@echo off
chcp 65001 >nul 2>&1
title 编外人员管理系统 - ARM镜像构建工具

:: 检查Docker
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 错误：未检测到Docker！
    echo 请先安装Docker Desktop: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

:menu
cls
echo ╔══════════════════════════════════════╗
echo ║  编外人员管理系统 - ARM镜像构建工具   ║
echo ╚══════════════════════════════════════╝
echo.
echo 请选择要构建的ARM镜像：
echo.
echo   [1] 🍎 ARM64 (Apple M1/M2/M3, 树莓派4/5, 华为鲲鹏)
echo   [2] 🥧 ARM32 (树莓派3/Zero/Zero W)
echo   [3] 🖥️  AMD64 (标准x86_64服务器)
echo   [4] 🌍 多架构镜像 (AMD64 + ARM64 + ARM32) ⭐推荐
echo   [5] 🚀 构建并推送到仓库
echo   [6] 🔧 本地测试ARM镜像 (QEMU模拟)
echo   [7] 📋 查看已构建的镜像
echo   [0] ❌ 退出
echo.
set /p choice=请输入选项编号 (0-7): 

if "%choice%"=="1" goto arm64
if "%choice%"=="2" goto arm32
if "%choice%"=="3" goto amd64
if "%choice%"=="4" goto multi
if "%choice%"=="5" goto push
if "%choice%"=="6" goto test
if "%choice%"=="7" goto list
if "%choice%"=="0" goto end

echo ⚠️ 无效选项，请重新选择
timeout /t 2 >nul
goto menu

:arm64
echo.
echo ========================================
echo   🏗️  构建 ARM64 镜像...
echo ========================================
echo.
echo 目标平台: linux/arm64 (aarch64)
echo 适用设备:
echo   - Apple Silicon Mac (M1/M2/M3)
echo   - 树莓派 4/5 / 400/CM4
echo   - 华为鲲鹏服务器
echo   - AWS Graviton实例
echo.

:: 使用ARM优化的Dockerfile（如果存在）
if exist "Dockerfile.arm" (
    set DOCKERFILE=-f Dockerfile.arm
    echo ✓ 使用ARM优化版 Dockerfile.arm
) else (
    set DOCKERFILE=-f Dockerfile
    echo ✓ 使用默认 Dockerfile
)

docker buildx build --platform linux/arm64 ^
    -t bwryglxt/salary-system:1.0.0-arm ^
    -t bwryglxt/salary-system:latest-arm ^
    %DOCKERFILE% ^
    --load ^
    .

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ ARM64镜像构建成功！
    echo.
    echo 📦 镜像标签:
    echo    bwryglxt/salary-system:1.0.0-arm
    echo    bwryglxt/salary-system:latest-arm
    echo.
    
    for /f "tokens=3 delims= " %%A in ('docker images bwryglxt/salary-system:1.0.0-arm ^| findstr /r "[0-9]* MB\|[0-9]* GB"') do (
        if not "%%A"=="SIZE" echo    大小: %%A
    )
) else (
    echo ❌ 构建失败！
)
echo.
pause
goto menu

:arm32
echo.
echo ========================================
echo   🏗️  构建 ARM32 镜像...
echo ========================================
echo.
echo 目标平台: linux/arm/v7 (armv7l)
echo 适用设备:
echo   - 树莓派 3B/3B+/Zero/Zero W
echo   - Orange Pi Zero
echo   - 其他ARM32开发板
echo.

if exist "Dockerfile.arm" (
    set DOCKERFILE=-f Dockerfile.arm
) else (
    set DOCKERFILE=-f Dockerfile
)

docker buildx build --platform linux/arm/v7 ^
    -t bwryglxt/salary-system:1.0.0-arm32 ^
    -t bwryglxt/salary-system:latest-arm32 ^
    %DOCKERFILE% ^
    --load ^
    .

if %ERRORLEVEL% EQU 0 (
    echo ✅ ARM32镜像构建成功！
) else (
    echo ❌ 构建失败！
)
echo.
pause
goto menu

:amd64
echo.
echo ========================================
echo   🏗️  构建 AMD64 镜像...
echo ========================================
echo.

docker buildx build --platform linux/amd64 ^
    -t bwryglxt/salary-system:1.0.0-amd64 ^
    -t bwryglxt/salary-system:latest-amd64 ^
    -f Dockerfile ^
    --load ^
    .

if %ERRORLEVEL% EQU 0 (
    echo ✅ AMD64镜像构建成功！
) else (
    echo ❌ 构建失败！
)
echo.
pause
goto menu

:multi
echo.
echo ========================================
echo   🌍 构建多架构镜像...
echo ========================================
echo.
echo 将同时构建以下平台:
echo   ✓ linux/amd64  (x86_64服务器)
echo   ✓ linux/arm64  (Apple M系列/树莓派4+/鲲鹏)
echo   ✓ linux/arm/v7 (树莓派3及更早版本)
echo.
echo ⚠️ 注意: 多架构镜像主要用于推送，本地只能加载当前平台
echo.

set /p confirm=确认构建多架构镜像？(y/n): 
if /i not "%confirm%"=="y" goto menu

if exist "Dockerfile.arm" (
    set DOCKERFILE=-f Dockerfile.arm
) else (
    set DOCKERFILE=-f Dockerfile
)

docker buildx build ^
    --platform linux/amd64,linux/arm64,linux/arm/v7 ^
    -t bwryglxt/salary-system:1.0.0-multi ^
    -t bwryglxt/salary-system:latest-multi ^
    %DOCKERFILE% ^
    --load ^
    .

if %ERRORLEVEL% EQU 0 (
    echo ✅ 多架构镜像构建成功！
) else (
    echo ❌ 构建失败！
)
echo.
pause
goto menu

:push
echo.
echo ========================================
echo   🚀 构建并推送到仓库
echo ========================================
echo.
echo 这将构建多架构镜像并推送到Docker Hub或私有仓库
echo.
set REGISTRY=docker.io
set /p REGISTRY=请输入仓库地址 (默认 docker.io): 

if "%REGISTRY%"=="" set REGISTRY=docker.io

echo.
echo 目标仓库: %REGISTRY%/bwryglxt/salary-system
echo 构建平台: linux/amd64,linux/arm64,linux/arm/v7
echo.
set /p confirm2=确认推送？(y/n): 
if /i not "%confirm2%"=="y" goto menu

echo.
echo 正在构建并推送（这可能需要10-30分钟）...

if exist "Dockerfile.arm" (
    set DOCKERFILE=-f Dockerfile.arm
) else (
    set DOCKERFILE=-f Dockerfile
)

docker buildx build ^
    --platform linux/amd64,linux/arm64,linux/arm/v7 ^
    -t %REGISTRY%/bwryglxt/salary-system:1.0.0 ^
    -t %REGISTRY%/bwryglxt/salary-system:latest ^
    %DOCKERFILE% ^
    --push ^
    .

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ 推送成功！
    echo.
    echo 📦 镜像地址:
    echo    %REGISTRY%/bwryglxt/salary-system:1.0.0
    echo    %REGISTRY%/bwryglxt/salary-system:latest
    echo.
    echo 📥 在其他设备上拉取:
    echo    docker pull %REGISTRY%/bwryglxt/salary-system:1.0.0
) else (
    echo ❌ 构建或推送失败！
)
echo.
pause
goto menu

:test
echo.
echo ========================================
echo   🔧 本地测试ARM镜像 (QEMU模拟)
echo ========================================
echo.
echo 将使用QEMU用户态模拟运行ARM容器
echo ⚠️ 性能会比原生慢10-50倍（仅用于测试）
echo.

:: 检查是否有ARM镜像
docker images | findstr "salary-system.*arm" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ 未找到ARM镜像，先构建一个...
    call :arm64
)

echo 启动ARM64测试容器...
docker run -d ^
    --platform linux/arm64 ^
    --name bwryglxt-test-arm ^
    -p 5051:5050 ^
    -v salary-data-arm-test:/app/data ^
    bwryglxt/salary-system:1.0.0-arm

if %ERRORLEVEL% EQU 0 (
    timeout /t 5 >nul
    
    :: 健康检查
    curl -sf http://localhost:5051/ >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ✅ ARM容器运行成功！
        echo.
        echo 🌐 访问地址: http://localhost:5051
        echo 📦 容器名称: bwryglxt-test-arm
        
        :: 尝试打开浏览器
        start http://localhost:5051
    ) else (
        echo ⚠️ 容器已启动但可能还在初始化
        echo    查看日志: docker logs bwryglxt-test-arm
    )
) else (
    echo ❌ 启动失败
)
echo.
pause
goto menu

:list
echo.
echo ========================================
echo   📋 已构建的镜像列表
echo ========================================
echo.
docker images | findstr "REPOSITORY bwryglxt"
echo.
echo BuildX构建器状态:
docker buildx ls
echo.
pause
goto menu

:end
echo.
echo 👋 再见！
exit /b 0
