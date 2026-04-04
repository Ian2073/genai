@echo off
setlocal EnableExtensions
TITLE GenAI Start (Unified Local)

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

set "MODE=terminal"
set "AUTO_DASHBOARD=1"
set "DASH_ARGS="
set "EVAL_ARGS="
set "COMPAT_GENAI_ONLY=0"
set "COMPAT_WITH_EVAL=0"

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
if /I "%~1"=="--eval-only" (
	set "MODE=eval"
	shift
	goto :collect_eval_args
)
if /I "%~1"=="--genai-only" (
	set "COMPAT_GENAI_ONLY=1"
	shift
	goto :parse_args
)
if /I "%~1"=="--with-eval" (
	set "COMPAT_WITH_EVAL=1"
	shift
	goto :parse_args
)
set "DASH_ARGS=%DASH_ARGS% %1"
shift
goto :parse_args

:collect_eval_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--stories" (
	if "%~2"=="" (
		echo [ERROR] --stories requires a path argument.
		exit /b 2
	)
	set "EVAL_ARGS=%EVAL_ARGS% --input %2"
	shift
	shift
	goto :collect_eval_args
)
set "EVAL_ARGS=%EVAL_ARGS% %1"
shift
goto :collect_eval_args

:args_done

set "AUTO_ENV_DIR=genai_env"
set "AUTO_ACTIVATE=%PROJECT_DIR%%AUTO_ENV_DIR%\Scripts\activate.bat"
set "AUTO_PY=%PROJECT_DIR%%AUTO_ENV_DIR%\Scripts\python.exe"

if /I "%MODE%"=="eval" goto :eval

if /I "%MODE%"=="dashboard" goto :dashboard

echo ====================================================
echo   GenAI Local Terminal Mode (Unified)
echo ====================================================
echo.
if "%COMPAT_GENAI_ONLY%"=="1" echo [INFO] --genai-only is now a no-op in local mode (single unified entrypoint).
if "%COMPAT_WITH_EVAL%"=="1" echo [INFO] --with-eval is now a no-op in local mode. Use --eval-only to run evaluation.
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
	echo   Start_GenAI.bat --eval-only --input output --branch auto --post-process none
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
echo   GenAI Local Dashboard Mode (Unified)
echo ====================================================
echo.
if "%COMPAT_GENAI_ONLY%"=="1" echo [INFO] --genai-only is now a no-op in local mode (single unified entrypoint).
if "%COMPAT_WITH_EVAL%"=="1" echo [INFO] --with-eval is now a no-op in local mode. Use --eval-only to run evaluation.
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

:eval
echo ====================================================
echo   GenAI Unified Eval Mode
echo ====================================================
echo.

if "%COMPAT_GENAI_ONLY%"=="1" echo [INFO] --genai-only ignored in --eval-only mode.
if "%COMPAT_WITH_EVAL%"=="1" echo [INFO] --with-eval ignored in --eval-only mode.

if "%EVAL_ARGS%"=="" (
	set "EVAL_ARGS= --input output --branch auto --post-process none"
	set "EVAL_DEFAULT=1"
) else (
	set "EVAL_DEFAULT=0"
)

if "%EVAL_DEFAULT%"=="1" (
	echo [INFO] No eval args supplied. Using default:%EVAL_ARGS%
)

if exist "%AUTO_PY%" (
	echo Running: "%AUTO_PY%" evaluation\main.py%EVAL_ARGS%
	"%AUTO_PY%" evaluation\main.py%EVAL_ARGS%
	if errorlevel 1 goto :fail_with_last_code
	endlocal
	goto :eof
)

echo [INFO] Auto environment not found, fallback to conda env: genai
conda run -n genai python evaluation\main.py%EVAL_ARGS%
if errorlevel 1 goto :fail_with_last_code
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

:fail_with_last_code
echo.
echo [ERROR] Command failed with exit code %ERRORLEVEL%.
exit /b %ERRORLEVEL%

:launch_dashboard_window
echo [INFO] Launching dashboard in a separate window...
start "GenAI Dashboard (Local)" cmd /c call "%~f0" --dashboard %DASH_ARGS%
goto :eof
