# Blog Editor — 启动入口脚本 (Windows PowerShell)
# 用法:
#   .\start.ps1                交互式菜单
#   .\start.ps1 start [-Port N]
#   .\start.ps1 stop
#   .\start.ps1 restart [-Port N]
#   .\start.ps1 status
#   .\start.ps1 install
#   .\start.ps1 check
#
# 如遇执行策略阻止: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV_DIR = Join-Path $env:USERPROFILE "venv"
$VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"

# ── venv ──
function Ensure-Venv {
    if (Test-Path (Join-Path $VENV_DIR "Scripts\pip.exe")) { return }
    if (Test-Path $VENV_DIR) {
        Write-Host "检测到不完整的虚拟环境，重建..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $VENV_DIR
    }
    Write-Host "创建 Python 虚拟环境: $VENV_DIR"
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pyCmd) {
        Write-Host "未找到 python，请先安装 Python 3.10+" -ForegroundColor Red
        Write-Host "https://www.python.org/downloads/"
        exit 1
    }
    & python -m venv $VENV_DIR
    if ($LASTEXITCODE -ne 0) { exit 1 }
    Write-Host "虚拟环境就绪" -ForegroundColor Green
}

function Invoke-ServerManager {
    param([string]$Action, [int]$Port = 9176)
    & $VENV_PYTHON (Join-Path $ROOT "server_manager.py") $Action --port $Port
}

function Install-Deps {
    $req = Join-Path $ROOT "requirements.txt"
    if (Test-Path $req) {
        Write-Host "安装依赖: requirements.txt"
        & $VENV_PYTHON -m pip install -r $req
    } else {
        Write-Host "无 requirements.txt（本项目仅用 Python 标准库）" -ForegroundColor DarkGray
    }
}

function Show-Check {
    Write-Host "===== Blog Editor 环境检测 ====="
    Write-Host "ROOT:        $ROOT"
    Write-Host "VENV:        $VENV_DIR"
    $py = Get-Command python -ErrorAction SilentlyContinue
    Write-Host ("python:      " + ($(if ($py) { $py.Source } else { "未找到" })))
    if (Test-Path $VENV_PYTHON) {
        & $VENV_PYTHON --version
    } else {
        Write-Host "venv Python: (未创建)" -ForegroundColor DarkGray
    }
    Write-Host ""
    & $VENV_PYTHON (Join-Path $ROOT "server_manager.py") status 2>$null
    Write-Host ""
    Write-Host "同级目录 (博客候选):"
    $count = 0
    Get-ChildItem (Split-Path $ROOT) -Directory | Where-Object {
        $_.Name -ne (Split-Path $ROOT -Leaf) -and $_.Name -notmatch '^\.' -and $_.Name -ne 'venv'
    } | ForEach-Object {
        $count++
        if (Test-Path (Join-Path $_.FullName ".blog.yaml")) {
            Write-Host "  ✓ $($_.Name)  (已配置博客)" -ForegroundColor Green
        } else {
            Write-Host "  - $($_.Name)"
        }
    }
    Write-Host "  共 $count 个兄弟目录"
}

# ── 菜单 ──
function Show-Menu {
    Clear-Host
    Write-Host "===================================="
    Write-Host "     Blog Editor"
    Write-Host "===================================="
    Write-Host "  1) 启动 server (port 9176)"
    Write-Host "  2) 停止 server"
    Write-Host "  3) 重启 server"
    Write-Host "  4) 运行状态"
    Write-Host "  5) 安装 Python 依赖"
    Write-Host "  6) 环境检测"
    Write-Host "  0) 退出"
    Write-Host "===================================="
}

function Run-Menu {
    Ensure-Venv
    while ($true) {
        Show-Menu
        $choice = Read-Host "请选择 [0-6]"
        switch ($choice) {
            "1" { Invoke-ServerManager start 9176 }
            "2" { Invoke-ServerManager stop  9176 }
            "3" { Invoke-ServerManager restart 9176 }
            "4" { Invoke-ServerManager status 9176 }
            "5" { Install-Deps }
            "6" { Show-Check }
            "0" { Write-Host "再见！"; exit 0 }
            default { Write-Host "无效选项" -ForegroundColor Red }
        }
        Write-Host ""
        Read-Host "按 Enter 返回..." | Out-Null
    }
}

# ── 命令行分发 ──
if ($MyInvocation.MyCommand.Name -match '\.ps1$') {
    $cmd = if ($args.Count -gt 0) { $args[0] } else { "" }
    $portArg = 9176
    if ($args -contains "--port") {
        $idx = [array]::IndexOf($args, "--port")
        if ($idx + 1 -lt $args.Count) { $portArg = [int]$args[$idx + 1] }
    }

    if ($cmd -eq "") {
        Run-Menu
    } elseif (@("start","stop","restart","status") -contains $cmd) {
        Ensure-Venv
        Invoke-ServerManager $cmd $portArg
    } elseif ($cmd -eq "install") {
        Ensure-Venv; Install-Deps
    } elseif ($cmd -eq "check") {
        Ensure-Venv; Show-Check
    } else {
        Write-Host "用法: .\start.ps1 {start|stop|restart|status|install|check}"
        Write-Host "  start  [-Port N]"
        Write-Host "  restart [-Port N]"
        exit 1
    }
}
