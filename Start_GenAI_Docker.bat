@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
title 故事生成系統 - Docker 啟動入口

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

set "MODE=terminal"
set "AUTO_DASHBOARD=1"
set "DASH_ARGS="

:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--dashboard" (
    set "MODE=dashboard"
    shift
    goto :parse_args
)
if /I "%~1"=="--no-dashboard" (
    set "AUTO_DASHBOARD=0"
    shift
    goto :parse_args
)
set "DASH_ARGS=%DASH_ARGS% %~1"
shift
goto :parse_args

:args_done

set "HOST_PORT=8765"
set "PREV="
for %%A in (%DASH_ARGS%) do (
    if defined PREV (
        if /I "!PREV!"=="--dashboard-port" set "HOST_PORT=%%~A"
        set "PREV="
    ) else (
        if /I "%%~A"=="--dashboard-port" set "PREV=--dashboard-port"
    )
)

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

docker image inspect genai:latest >nul 2>&1
if errorlevel 1 (
    echo [INFO] Docker image genai:latest not found. Running build first...
    if not exist "%PROJECT_DIR%Build_GenAI_Docker.bat" (
        echo [ERROR] Build_GenAI_Docker.bat not found.
        goto :fail
    )
    call "%PROJECT_DIR%Build_GenAI_Docker.bat"
    if errorlevel 1 goto :fail
) else (
    echo [INFO] Using existing image: genai:latest
    echo        To rebuild image, run Build_GenAI_Docker.bat
)

echo.
if /I "%MODE%"=="dashboard" goto :dashboard

echo ====================================================
echo   Docker Terminal Mode
echo ====================================================
echo Service : genai
echo Project : /app
echo Models  : /app/models ^(read-only^)
echo Output  : /app/output
echo Logs    : /app/logs
echo Runs    : /app/runs
echo.
if "%AUTO_DASHBOARD%"=="1" (
    call :launch_dashboard_window
)
echo Tip: enter ^'exit^' to leave the shell.
echo Tip: use --no-dashboard to keep terminal only.
echo.
docker compose run --rm --entrypoint /bin/bash genai
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto :fail_with_code
exit /b 0

:dashboard
echo ====================================================
echo   Docker Dashboard Mode
echo ====================================================
echo URL: http://127.0.0.1:%HOST_PORT%
echo Press Ctrl+C to stop.
echo.
docker compose run --rm -p %HOST_PORT%:%HOST_PORT% genai --dashboard --dashboard-host 0.0.0.0 %DASH_ARGS%
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto :fail_with_code
exit /b 0

:launch_dashboard_window
echo [INFO] 另開視窗啟動 Dashboard...
start "GenAI Docker Dashboard" cmd /c call "%~f0" --dashboard %DASH_ARGS%
goto :eof

:fail
echo.
echo Press any key to close this window...
pause >nul
exit /b 1

:fail_with_code
echo.
echo [ERROR] Docker mode exited with code %EXIT_CODE%.
echo Press any key to close this window...
pause >nul
exit /b %EXIT_CODE%
