@echo off
setlocal EnableExtensions
TITLE GenAI Start (Unified Local)

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

set "MODE=demo"
set "AUTO_DASHBOARD=0"
set "DASH_ARGS="
set "EVAL_ARGS="
set "COMPAT_GENAI_ONLY=0"
set "COMPAT_WITH_EVAL=0"
set "FORCE_NON_DASHBOARD=0"

:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--dashboard" (
	set "MODE=dashboard"
	shift
	goto :parse_args
)
if /I "%~1"=="--terminal" (
	set "MODE=terminal"
	shift
	goto :parse_args
)
if /I "%~1"=="--dashboard-status" (
	set "MODE=dashboard_status"
	shift
	goto :parse_args
)
if /I "%~1"=="--dashboard-stop" (
	set "MODE=dashboard_stop"
	shift
	goto :parse_args
)
if /I "%~1"=="--dashboard-restart" (
	set "MODE=dashboard_restart"
	shift
	goto :parse_args
)
if /I "%~1"=="--force-non-dashboard" (
	set "FORCE_NON_DASHBOARD=1"
	shift
	goto :parse_args
)
if /I "%~1"=="--no-dashboard" (
	set "AUTO_DASHBOARD=0"
	shift
	goto :parse_args
)
if /I "%~1"=="--demo" (
	set "MODE=demo"
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

if /I "%MODE%"=="toggle_dashboard" goto :toggle_dashboard
if /I "%MODE%"=="dashboard" goto :dashboard
if /I "%MODE%"=="dashboard_status" goto :dashboard_status
if /I "%MODE%"=="dashboard_stop" goto :dashboard_stop
if /I "%MODE%"=="dashboard_restart" goto :dashboard_restart
if /I "%MODE%"=="demo" goto :demo
if /I "%MODE%"=="terminal" goto :terminal

:demo
echo ====================================================
echo   GenAI Demo Recording Setup
echo ====================================================
echo.
set DEMO_MODE=1
echo [READY] This window will not start generation automatically.
echo [READY] Start screen recording first, then run the command below.
echo.
if exist "%AUTO_ACTIVATE%" (
	echo [INFO] Activating auto environment: %AUTO_ENV_DIR%
	call "%AUTO_ACTIVATE%"
	if errorlevel 1 (
		echo [ERROR] genai_env activation failed.
		goto :fail
	)
	echo.
	echo Demo command:
	echo   python scripts\terminal_demo.py%DASH_ARGS%
	echo.
	cmd /k
	endlocal
	goto :eof
)

echo [INFO] Auto environment not found, activating conda env: genai
call conda activate genai
if errorlevel 1 (
	echo [ERROR] conda env "genai" not found or activation failed.
	goto :fail
)
echo.
echo Demo command:
echo   python scripts\terminal_demo.py%DASH_ARGS%
echo.
cmd /k
endlocal
goto :eof

:terminal
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
	if errorlevel 1 (
		echo [ERROR] genai_env activation failed.
		goto :fail
	)
	call :print_python_identity_shell
	echo.
	echo Environment ready. You can run:
	echo   python chief.py --count 1
	echo   python -m pipeline --dashboard
	echo   Start_GenAI.bat --dashboard-status
	echo   Start_GenAI.bat --dashboard-stop
	echo   Start_GenAI.bat --dashboard-restart
	echo   Start_GenAI.bat --eval-only --input output --branch auto --post-process none
	echo.
	cmd /k
	endlocal
	goto :eof
)

	echo [INFO] Auto environment not found, using Conda env: genai
call conda activate genai
if errorlevel 1 (
	echo [ERROR] conda env "genai" not found or activation failed.
	goto :fail
)
call :print_python_identity_shell
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
echo Press Ctrl+C once to stop. Cleanup verification will run automatically.
echo.
echo [PRECHECK] Clearing stale dashboard listener on port 8765...
call :run_dashboard_lifecycle stop
if errorlevel 1 (
	echo [ERROR] Failed to clear dashboard listener. You can inspect with:
	echo   Start_GenAI.bat --dashboard-status
	goto :fail_with_last_code
)

if exist "%AUTO_PY%" (
	echo [1/1] Using auto environment python
	call :print_python_identity_with "%AUTO_PY%"
	"%AUTO_PY%" -m pipeline --dashboard %DASH_ARGS%
	if errorlevel 1 (
		echo [WARN] Dashboard process exited with non-zero code.
		call :post_dashboard_cleanup
		if errorlevel 1 echo [WARN] Cleanup verification found residual listeners.
		endlocal & exit /b 1
	)
	call :post_dashboard_cleanup
	if errorlevel 1 echo [WARN] Cleanup verification found residual listeners.
	endlocal & exit /b 0
)

echo [INFO] Auto environment not found, using conda env: genai
conda run -n genai python -c "import platform,sys; print('[INFO] Python executable:', sys.executable); print('[INFO] Python version:', platform.python_version())"
conda run -n genai python -m pipeline --dashboard %DASH_ARGS%
if errorlevel 1 (
	echo [WARN] Dashboard process exited with non-zero code.
	call :post_dashboard_cleanup
	if errorlevel 1 echo [WARN] Cleanup verification found residual listeners.
	goto :fail_with_last_code
)
call :post_dashboard_cleanup
if errorlevel 1 echo [WARN] Cleanup verification found residual listeners.
endlocal
goto :eof

:dashboard_status
echo ====================================================
echo   GenAI Dashboard Status
echo ====================================================
echo.
call :run_dashboard_lifecycle status
set "CMD_EXIT=%ERRORLEVEL%"
endlocal & exit /b %CMD_EXIT%

:dashboard_stop
echo ====================================================
echo   GenAI Dashboard Stop
echo ====================================================
echo.
call :run_dashboard_lifecycle stop
set "CMD_EXIT=%ERRORLEVEL%"
if "%CMD_EXIT%"=="0" echo [INFO] Dashboard stop check complete.
endlocal & exit /b %CMD_EXIT%

:dashboard_restart
echo ====================================================
echo   GenAI Dashboard Restart
echo ====================================================
echo.
call :run_dashboard_lifecycle stop
if errorlevel 1 goto :fail_with_last_code
goto :dashboard

:toggle_dashboard
echo ====================================================
echo   GenAI One-Click Toggle
echo ====================================================
echo.
call :is_dashboard_running
if "%DASH_RUNNING%"=="1" (
	echo [INFO] Dashboard detected on port 8765. Closing now...
	call :run_dashboard_lifecycle stop
	set "CMD_EXIT=%ERRORLEVEL%"
	if "%CMD_EXIT%"=="0" echo [DONE] Dashboard closed.
	endlocal & exit /b %CMD_EXIT%
)
echo [INFO] Dashboard not running. Opening now...
goto :dashboard

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
	call :print_python_identity_with "%AUTO_PY%"
	echo Running: "%AUTO_PY%" evaluation\main.py%EVAL_ARGS%
	"%AUTO_PY%" evaluation\main.py%EVAL_ARGS%
	if errorlevel 1 goto :fail_with_last_code
	endlocal
	goto :eof
)

echo [INFO] Auto environment not found, fallback to conda env: genai
conda run -n genai python -c "import platform,sys; print('[INFO] Python executable:', sys.executable); print('[INFO] Python version:', platform.python_version())"
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

:run_dashboard_lifecycle
set "LIFE_CMD=%~1"
if "%LIFE_CMD%"=="" set "LIFE_CMD=status"
set "LIFE_ARGS=--port 8765"
if /I "%LIFE_CMD%"=="stop" (
	if "%FORCE_NON_DASHBOARD%"=="1" set "LIFE_ARGS=%LIFE_ARGS% --force-non-dashboard"
)
if exist "%AUTO_PY%" (
	"%AUTO_PY%" scripts\dashboard_lifecycle.py %LIFE_CMD% %LIFE_ARGS%
	goto :eof
)
conda run -n genai python scripts\dashboard_lifecycle.py %LIFE_CMD% %LIFE_ARGS%
goto :eof

:post_dashboard_cleanup
echo [CLEANUP] Verifying complete dashboard shutdown...
set "KEEP_FORCE_FLAG=%FORCE_NON_DASHBOARD%"
set "FORCE_NON_DASHBOARD=1"
call :run_dashboard_lifecycle stop
set "POST_EXIT=%ERRORLEVEL%"
set "FORCE_NON_DASHBOARD=%KEEP_FORCE_FLAG%"
if "%POST_EXIT%"=="0" (
	echo [CLEANUP] Port 8765 is clear.
) else (
	echo [CLEANUP] Port check failed; run Start_GenAI.bat --dashboard-stop once.
)
exit /b %POST_EXIT%

:print_python_identity_shell
python -c "import platform,sys; print('[INFO] Python executable:', sys.executable); print('[INFO] Python version:', platform.python_version())"
goto :eof

:print_python_identity_with
set "IDENT_PY=%~1"
if not exist "%IDENT_PY%" (
	echo [WARN] Python executable not found: %IDENT_PY%
	goto :eof
)
"%IDENT_PY%" -c "import platform,sys; print('[INFO] Python executable:', sys.executable); print('[INFO] Python version:', platform.python_version())"
goto :eof

:is_dashboard_running
set "DASH_RUNNING=0"
set "TMP_STATUS=%TEMP%\genai_dashboard_status_%RANDOM%_%RANDOM%.json"
if exist "%AUTO_PY%" (
	"%AUTO_PY%" scripts\dashboard_lifecycle.py status --port 8765 > "%TMP_STATUS%" 2>nul
) else (
	conda run -n genai python scripts\dashboard_lifecycle.py status --port 8765 > "%TMP_STATUS%" 2>nul
)
findstr /C:"\"dashboard_like\": true" "%TMP_STATUS%" >nul 2>nul
if not errorlevel 1 set "DASH_RUNNING=1"
if exist "%TMP_STATUS%" del /f /q "%TMP_STATUS%" >nul 2>nul
goto :eof
