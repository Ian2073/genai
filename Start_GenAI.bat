@echo off
setlocal EnableExtensions
TITLE GenAI Start (Local)

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

set "AUTO_ENV_DIR=genai_env"
set "AUTO_ACTIVATE=%PROJECT_DIR%%AUTO_ENV_DIR%\Scripts\activate.bat"
set "AUTO_PY=%PROJECT_DIR%%AUTO_ENV_DIR%\Scripts\python.exe"

if /I "%MODE%"=="dashboard" goto :dashboard

echo ====================================================
echo   GenAI Local Terminal Mode
echo ====================================================
echo.
if "%AUTO_DASHBOARD%"=="1" (
	call :launch_dashboard_window
)
if exist "%AUTO_ACTIVATE%" (
	echo [1/1] Activating auto environment: %AUTO_ENV_DIR%
	call "%AUTO_ACTIVATE%"
	if errorlevel 1 goto :fail
	echo.
	echo Environment ready. You can run:
	echo   python chief.py --count 1
	echo   python -m pipeline --dashboard
	echo   Start_GenAI.bat --no-dashboard
	echo.
	cmd /k
	endlocal
	goto :eof
)

echo [1/1] Auto environment not found, trying Conda env: genai
call conda activate genai
if errorlevel 1 goto :fail
echo.
echo Environment ready ^(conda: genai^).
echo.
cmd /k
endlocal
goto :eof

:dashboard
echo ====================================================
echo   GenAI Local Dashboard Mode
echo ====================================================
echo.
echo Dashboard URL default: http://127.0.0.1:8765
echo Press Ctrl+C to stop.
echo.
if exist "%AUTO_PY%" (
	echo [1/2] Using auto environment python
	"%AUTO_PY%" -m pipeline --dashboard %DASH_ARGS%
	if not errorlevel 1 (
		endlocal
		goto :eof
	)
	echo.
	echo [WARN] Auto environment launch failed, fallback to conda env: genai
)

echo [2/2] Running dashboard with conda env: genai
conda run -n genai python -m pipeline --dashboard %DASH_ARGS%
if errorlevel 1 goto :fail

endlocal
goto :eof

:fail
echo.
echo [ERROR] Failed to start local mode.
echo Please verify either:
echo   - genai_env exists, or
echo   - conda env "genai" is available.
echo.
echo Press any key to close this window...
pause >nul
exit /b 1

:launch_dashboard_window
echo [INFO] Launching dashboard in a separate window...
start "GenAI Dashboard (Local)" cmd /c call "%~f0" --dashboard %DASH_ARGS%
goto :eof
