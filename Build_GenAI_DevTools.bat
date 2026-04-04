@echo off
setlocal EnableExtensions
TITLE GenAI DevTools Check and Repair

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "AUTO_ENV_DIR=genai_env"
set "VCVARS_BAT="
set "PREFERRED_VCVARS_VER=14.44"
set "VCVARS_USED_VER=default"
set "CHECK_STATUS=0"

call :find_vcvars

echo ====================================================
echo   GenAI DevTools Check and Repair
echo ====================================================

if defined VCVARS_BAT (
    echo [1/3] Loading MSVC build tools...
    if defined PREFERRED_VCVARS_VER (
        call "%VCVARS_BAT%" -vcvars_ver=%PREFERRED_VCVARS_VER% >nul 2>&1
        if not errorlevel 1 (
            set "VCVARS_USED_VER=%PREFERRED_VCVARS_VER%"
        ) else (
            echo [WARN] Requested MSVC toolset %PREFERRED_VCVARS_VER% was not available, using default.
            call "%VCVARS_BAT%" >nul
        )
    ) else (
        call "%VCVARS_BAT%" >nul
    )
    if errorlevel 1 (
        echo [ERROR] Failed to load Visual C++ build tools.
        goto :fail
    )
) else (
    echo [WARN] Visual C++ build tools were not found.
    echo        Attempting automatic repair via Build_GenAI.bat...
    call :run_build_repair
    call :find_vcvars
    if defined VCVARS_BAT (
        call "%VCVARS_BAT%" -vcvars_ver=%PREFERRED_VCVARS_VER% >nul 2>&1
        if not errorlevel 1 set "VCVARS_USED_VER=%PREFERRED_VCVARS_VER%"
    )
)

where cl >nul 2>&1
if errorlevel 1 (
    echo [WARN] cl.exe is still not available on PATH.
    set "CHECK_STATUS=2"
) else (
    for /f "usebackq delims=" %%I in (`where cl 2^>nul`) do (
        echo   cl=%%I
        goto :cl_found
    )
)

:cl_found
echo [2/3] Checking auto environment python...
if not exist "%PROJECT_DIR%%AUTO_ENV_DIR%\Scripts\python.exe" (
    echo [WARN] Auto environment python was not found.
    echo        Attempting automatic repair via Build_GenAI.bat...
    call :run_build_repair
)

set "AUTO_PY=%PROJECT_DIR%%AUTO_ENV_DIR%\Scripts\python.exe"
set "PY_VER="
for /f "tokens=2 delims= " %%I in ('"%AUTO_PY%" --version 2^>nul') do set "PY_VER=%%I"
if defined PY_VER (
    echo   python=%PY_VER%
) else (
    echo [WARN] Failed to execute auto environment python.
    if "%CHECK_STATUS%"=="0" set "CHECK_STATUS=3"
)

echo [3/3] Running runtime diagnostics...
if exist "%AUTO_PY%" (
    "%AUTO_PY%" scripts\doctor.py --workspace-root . --expect-cuda auto >nul 2>&1
    if errorlevel 2 (
        echo [WARN] Doctor found critical runtime issues.
        if "%CHECK_STATUS%"=="0" set "CHECK_STATUS=4"
    ) else (
        echo   doctor=ok
    )
) else (
    echo [WARN] Doctor check skipped because auto environment python is missing.
    if "%CHECK_STATUS%"=="0" set "CHECK_STATUS=5"
)

echo.
echo ====================================================
echo   DevTools Check Result
if "%CHECK_STATUS%"=="0" (
    echo   status: PASS
) else (
    echo   status: WARN ^(exit code %CHECK_STATUS%^)
)
if defined VCVARS_BAT echo   MSVC tools: enabled
if /I not "%VCVARS_USED_VER%"=="default" echo   MSVC toolset: %VCVARS_USED_VER%
if not defined VCVARS_BAT echo   MSVC tools: not found
echo ====================================================
echo.
call :hold_and_exit %CHECK_STATUS%

:run_build_repair
call "%PROJECT_DIR%Build_GenAI.bat"
if errorlevel 1 (
    echo [WARN] Build_GenAI.bat repair attempt did not finish successfully.
)
goto :eof

:find_vcvars
for %%I in (
    "%ProgramFiles%\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\18\Professional\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\18\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
) do (
    if exist "%%~fI" (
        set "VCVARS_BAT=%%~fI"
        goto :eof
    )
)
goto :eof

:fail
echo.
call :hold_and_exit 1

:hold_and_exit
set "EXIT_CODE=%~1"
if /I not "%GENAI_DEVTOOLS_NO_HOLD%"=="1" (
    echo Press any key to close this window...
    pause >nul
)
exit /b %EXIT_CODE%
