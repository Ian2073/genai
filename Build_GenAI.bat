@echo off
setlocal EnableExtensions

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "AUTO_ENV_DIR=genai_env"
set "BASE_PY_EXE="
set "AUTO_INSTALL_MSVC_IF_MISSING=1"
set "SETUP_ARGS="

call :parse_args %*

call :resolve_python311
if not defined BASE_PY_EXE goto :python_missing

echo ====================================================
echo   GenAI Build (Local Environment)
echo ====================================================
echo This script auto-detects RTX 40/50 GPU and installs matching torch profile.
echo It also clears stale exllamav2 torch_extensions cache to avoid old MSVC linker artifacts.
echo Python 3.11: %BASE_PY_EXE%
echo Environment path: %AUTO_ENV_DIR%
echo.

if not exist "%PROJECT_DIR%models" (
    echo [WARN] models\ folder was not found.
    echo        Environment setup can continue, but runtime doctor will warn until models are copied.
    echo.
)

set "MSVC_HINT_BAT="
call :find_vcvars

where cl >nul 2>&1
if errorlevel 1 (
    if defined MSVC_HINT_BAT (
        echo [WARN] cl.exe was not found on PATH, but Visual Studio tools were detected.
        echo        Use Build_GenAI_DevTools.bat to load MSVC into this shell before JIT workflows.
    ) else (
        echo [WARN] cl.exe was not found on PATH.
        echo        The project can still install and run, but some exllamav2 first-run JIT paths may be limited.
        if /I "%AUTO_INSTALL_MSVC_IF_MISSING%"=="1" (
            echo [INFO] Trying to install Visual Studio C++ Build Tools automatically...
            call :install_msvc_build_tools
            call :find_vcvars
            if defined MSVC_HINT_BAT (
                echo [INFO] Visual Studio Build Tools were detected after installation.
                echo        Open Build_GenAI_DevTools.bat to load MSVC in a build-enabled shell.
            ) else (
                echo [WARN] Visual Studio Build Tools are still not detected.
                echo        Please install manually and run this script again.
            )
        ) else (
            echo        Auto-install is disabled by --no-install-msvc-if-missing.
        )
    )
    if exist "%PROJECT_DIR%Build_GenAI_DevTools.bat" (
        echo        After setup, use Build_GenAI_DevTools.bat when you need an MSVC-enabled shell.
    )
    echo.
) else (
    echo [INFO] cl.exe detected on PATH.
    echo.
)

"%BASE_PY_EXE%" scripts\setup_env.py --env-path "%AUTO_ENV_DIR%" --install-scope full --base-python "%BASE_PY_EXE%" %SETUP_ARGS%
if errorlevel 1 (
    echo.
    echo [ERROR] Environment setup failed.
    exit /b 1
)

set "GENAI_PY=%PROJECT_DIR%%AUTO_ENV_DIR%\Scripts\python.exe"
if not exist "%GENAI_PY%" set "GENAI_PY=%BASE_PY_EXE%"

echo.
echo [INFO] Running environment diagnostics...
set "DOCTOR_PY=%PROJECT_DIR%%AUTO_ENV_DIR%\Scripts\python.exe"
if not exist "%DOCTOR_PY%" set "DOCTOR_PY=%BASE_PY_EXE%"
"%DOCTOR_PY%" scripts\doctor.py --workspace-root . --expect-cuda auto
if errorlevel 2 (
    echo.
    echo [ERROR] Doctor found critical runtime issues.
    exit /b 2
)

echo.
echo [OK] Environment setup finished.
echo Next steps:
echo   1. Start_GenAI.bat
if exist "%PROJECT_DIR%Build_GenAI_DevTools.bat" echo   2. Build_GenAI_DevTools.bat  ^(optional MSVC-enabled shell^)
echo   3. %AUTO_ENV_DIR%\Scripts\activate
exit /b 0

:parse_args
if "%~1"=="" goto :eof
if /I "%~1"=="--install-msvc-if-missing" (
    set "AUTO_INSTALL_MSVC_IF_MISSING=1"
) else if /I "%~1"=="--no-install-msvc-if-missing" (
    set "AUTO_INSTALL_MSVC_IF_MISSING=0"
) else (
    set "SETUP_ARGS=%SETUP_ARGS% %1"
)
shift
goto :parse_args

:install_msvc_build_tools
where winget >nul 2>&1
if errorlevel 1 (
    echo [WARN] winget was not found. Cannot auto-install Visual Studio Build Tools.
    goto :eof
)

winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --accept-package-agreements --accept-source-agreements --override "--quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows11SDK.22621"
if errorlevel 1 (
    echo [WARN] Automatic MSVC installation failed. Try manual install from Visual Studio Installer.
    goto :eof
)
echo [INFO] Visual Studio Build Tools installation command completed.
goto :eof

:resolve_python311
for /f "usebackq delims=" %%I in (`py -3.11 -c "import sys; print(sys.executable)" 2^>nul`) do (
    set "BASE_PY_EXE=%%I"
    goto :eof
)

for /f "usebackq delims=" %%I in (`python -c "import sys; assert sys.version_info[:2]==(3,11); print(sys.executable)" 2^>nul`) do (
    set "BASE_PY_EXE=%%I"
    goto :eof
)

for %%I in (
    "%USERPROFILE%\miniconda3\envs\genai\python.exe"
    "%USERPROFILE%\anaconda3\envs\genai\python.exe"
    "%USERPROFILE%\miniforge3\envs\genai\python.exe"
    "C:\Python311\python.exe"
) do (
    if exist "%%~fI" (
        set "BASE_PY_EXE=%%~fI"
        goto :eof
    )
)
goto :eof

:find_vcvars
set "MSVC_HINT_BAT="

if defined VSINSTALLDIR (
    if exist "%VSINSTALLDIR%\VC\Auxiliary\Build\vcvars64.bat" (
        set "MSVC_HINT_BAT=%VSINSTALLDIR%\VC\Auxiliary\Build\vcvars64.bat"
        goto :eof
    )
)

set "VSWHERE_EXE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE_EXE%" set "VSWHERE_EXE=%ProgramFiles%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE_EXE%" (
    for /f "usebackq delims=" %%I in (`"%VSWHERE_EXE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul`) do (
        if exist "%%I\VC\Auxiliary\Build\vcvars64.bat" (
            set "MSVC_HINT_BAT=%%I\VC\Auxiliary\Build\vcvars64.bat"
            goto :eof
        )
    )
)

for %%I in (
    "%ProgramFiles(x86)%\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles(x86)%\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles(x86)%\Microsoft Visual Studio\18\Professional\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles(x86)%\Microsoft Visual Studio\18\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\18\Professional\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\18\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
) do (
    if exist "%%~fI" (
        set "MSVC_HINT_BAT=%%~fI"
        goto :eof
    )
)
goto :eof

:python_missing
echo ====================================================
echo   GenAI Build (Local Environment)
echo ====================================================
echo [ERROR] Python 3.11 executable was not found.
echo.
echo Install one of the following first, then run this script again:
echo   - Python 3.11 from python.org
echo   - py launcher with Python 3.11 available as "py -3.11"
echo   - Conda env named "genai" with Python 3.11
echo.
echo Recommended download:
echo   https://www.python.org/downloads/windows/
exit /b 1
