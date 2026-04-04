@echo off
chcp 65001 >nul
setlocal EnableExtensions
title 故事生成系統 - Docker 建置入口

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

set "MODEL_DIR=%PROJECT_DIR%models"
set "OUTPUT_DIR=%PROJECT_DIR%output"
set "LOGS_DIR=%PROJECT_DIR%logs"
set "RUNS_DIR=%PROJECT_DIR%runs"

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 找不到 docker，請先安裝 Docker Desktop。
    goto :fail
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 找不到 docker compose，請確認 Docker Desktop 已正確安裝。
    goto :fail
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker daemon 尚未啟動。
    echo         請先開啟 Docker Desktop，待狀態 Ready 後再重試。
    goto :fail
)

if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
if not exist "%RUNS_DIR%" mkdir "%RUNS_DIR%"

echo ====================================================
echo   Building Docker images (genai + evaluation)
echo ====================================================
if "%~1"=="" (
    docker compose build genai story-checker coref-service
) else (
    docker compose build %*
)
if errorlevel 1 (
    echo [ERROR] Docker image build failed.
    goto :fail
)

echo.
echo [OK] Docker build completed.
exit /b 0

:fail
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
