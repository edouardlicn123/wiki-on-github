@echo off
REM ========================================================
REM  Blog Editor — 启动入口脚本 (Windows CMD)
REM  用法:
REM    start.bat                  交互式菜单
REM    start.bat start [--port N]
REM    start.bat stop
REM    start.bat restart [--port N]
REM    start.bat status
REM    start.bat install
REM    start.bat check
REM ========================================================
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

REM ── venv（用户根目录下的 venv） ──
set "VENV_DIR=%USERPROFILE%\venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

call :ensure_venv
if errorlevel 1 goto :eof

if "%~1"=="" goto menu
goto dispatch

:ensure_venv
if exist "%VENV_DIR%\Scripts\pip.exe" goto :eof
if exist "%VENV_DIR%" (
    echo 检测到不完整的虚拟环境，重建...
    rmdir /s /q "%VENV_DIR%" 2>nul
)
echo 创建 Python 虚拟环境: %VENV_DIR%
where python >nul 2>&1 || (
    echo 未找到 python，请先安装 Python 3.10+
    echo https://www.python.org/downloads/
    exit /b 1
)
python -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo 创建虚拟环境失败
    exit /b 1
)
echo 虚拟环境就绪
goto :eof

:dispatch
set "CMD=%~1"
shift
if "%CMD%"=="start"      goto run_manager
if "%CMD%"=="stop"       goto run_manager
if "%CMD%"=="restart"    goto run_manager
if "%CMD%"=="status"     goto run_manager
if "%CMD%"=="install"    goto cmd_install
if "%CMD%"=="check"      goto cmd_check
echo 用法: start.bat {start^|stop^|restart^|status^|install^|check}
echo   start  [--port PORT]
echo   restart [--port PORT]
exit /b 1

:run_manager
"%VENV_PYTHON%" "%ROOT%\server_manager.py" %CMD% %*
exit /b %errorlevel%

:cmd_install
if exist "%ROOT%\requirements.txt" (
    echo 安装依赖: requirements.txt
    "%VENV_PYTHON%" -m pip install -r "%ROOT%\requirements.txt"
) else (
    echo 无 requirements.txt（本项目仅用 Python 标准库）
)
exit /b 0

:cmd_check
echo ===== Blog Editor 环境检测 =====
echo ROOT:        %ROOT%
echo VENV:        %VENV_DIR%
where python >nul 2>&1 && (
    for /f "delims=" %%i in ('where python') do echo python:     %%i & goto :got_python
    :got_python
) || echo python:     未找到
if exist "%VENV_PYTHON%" (
    for /f "delims=" %%v in ('"%VENV_PYTHON%" --version 2^>^&1') do echo venv Python: %%v
) else (
    echo venv Python: (未创建)
)
echo.
"%VENV_PYTHON%" "%ROOT%\server_manager.py" status 2>nul || echo server: 未运行
echo.
echo 同级目录 (博客候选):
set /a count=0
for /d %%d in ("%ROOT%\..\*") do (
    set "name=%%~nd"
    if not "!name!"=="wiki-on-github" (
        set /a count+=1
        if exist "%%d\.blog.yaml" (
            echo   ✓ !name!  (已配置博客)
        ) else (
            echo   - !name!
        )
    )
)
echo   共 %count% 个兄弟目录
exit /b 0

REM ── 交互式菜单 ──
:menu
cls
echo ====================================
echo      Blog Editor
echo ====================================
echo  1^) 启动 server (port 9176)
echo  2^) 停止 server
echo  3^) 重启 server
echo  4^) 运行状态
echo  5^) 安装 Python 依赖
echo  6^) 环境检测
echo  0^) 退出
echo ====================================
set /p choice="请选择 [0-6]: "

if "%choice%"=="1" "%VENV_PYTHON%" "%ROOT%\server_manager.py" start --port 9176
if "%choice%"=="2" "%VENV_PYTHON%" "%ROOT%\server_manager.py" stop
if "%choice%"=="3" "%VENV_PYTHON%" "%ROOT%\server_manager.py" restart --port 9176
if "%choice%"=="4" "%VENV_PYTHON%" "%ROOT%\server_manager.py" status 2>nul || echo server 未运行
if "%choice%"=="5" call :cmd_install
if "%choice%"=="6" call :cmd_check
if "%choice%"=="0" (
    echo 再见！
    exit /b 0
)
echo.
pause
goto menu
