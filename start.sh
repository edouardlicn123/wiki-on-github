#!/bin/bash
# Blog Editor — 启动入口脚本（Linux / macOS）
# 用法:
#   start.sh                 交互式菜单
#   start.sh start [--port N]
#   start.sh stop
#   start.sh restart [--port N]
#   start.sh status
#   start.sh install
#   start.sh check

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CMD="${1:-}"
shift || true

# ── venv（复用用户根目录的 ~/venv） ──
VENV_DIR="$HOME/venv"
VENV_PYTHON="$VENV_DIR/bin/python3"

ensure_venv() {
    if [ -d "$VENV_DIR" ] && [ ! -f "$VENV_DIR/bin/pip" ]; then
        echo "检测到不完整的虚拟环境（缺少 pip），重建..."
        rm -rf "$VENV_DIR"
    fi
    if [ ! -d "$VENV_DIR" ]; then
        echo "创建 Python 虚拟环境: $VENV_DIR"
        python3 -m venv "$VENV_DIR" || {
            echo "创建失败，尝试安装 python3-venv..."
            sudo apt-get install -y python3-venv 2>/dev/null || sudo yum install -y python3-venv 2>/dev/null || {
                echo "请手动安装 python3-venv: sudo apt install python3-venv"
                exit 1
            }
            python3 -m venv "$VENV_DIR" || exit 1
        }
    fi
}

cmd_install() {
    ensure_venv
    if [ -f "$ROOT/requirements.txt" ]; then
        echo "安装依赖: requirements.txt"
        "$VENV_PYTHON" -m pip install -r "$ROOT/requirements.txt"
    else
        echo "无 requirements.txt（本项目仅用 Python 标准库）"
    fi
}

cmd_check() {
    echo "===== Blog Editor 环境检测 ====="
    echo "ROOT:        $ROOT"
    echo "VENV:        $VENV_DIR"
    echo "python3:     $(which python3 2>/dev/null || echo '未找到')"
    if [ -d "$VENV_DIR" ]; then
        echo "venv Python: $VENV_PYTHON → $("$VENV_PYTHON" --version 2>/dev/null || echo '坏了')"
    else
        echo "venv Python: (未创建)"
    fi
    echo ""
    "$VENV_PYTHON" "$ROOT/server_manager.py" status || true
    echo ""
    echo "同级目录 (博客候选):"
    local siblings=0
    for d in "$ROOT"/../*/; do
        [ -d "$d" ] || continue
        local name
        name="$(basename "$d")"
        [[ "$name" == .* ]] && continue
        [ "$name" == "$(basename "$ROOT")" ] && continue
        [ "$name" == "venv" ] && continue
        siblings=$((siblings + 1))
        if [ -f "$d/.blog.yaml" ]; then
            echo "  ✓ $name  (已配置博客)"
        else
            echo "  - $name"
        fi
    done
    echo "  共 $siblings 个兄弟目录"
}

# ── 交互式菜单 ──
show_menu() {
    clear
    echo "===================================="
    echo "     Blog Editor"
    echo "===================================="
    echo " 1) 启动 server (port 9176)"
    echo " 2) 停止 server"
    echo " 3) 重启 server"
    echo " 4) 运行状态"
    echo " 5) 安装 Python 依赖"
    echo " 6) 环境检测"
    echo " 0) 退出"
    echo "===================================="
    echo -n "请选择 [0-6]: "
}

run_menu() {
    ensure_venv
    while true; do
        show_menu
        read -r choice
        case "$choice" in
            1) "$VENV_PYTHON" "$ROOT/server_manager.py" start --port 9176 ;;
            2) "$VENV_PYTHON" "$ROOT/server_manager.py" stop ;;
            3) "$VENV_PYTHON" "$ROOT/server_manager.py" restart --port 9176 ;;
            4) "$VENV_PYTHON" "$ROOT/server_manager.py" status || true ;;
            5) cmd_install ;;
            6) cmd_check ;;
            0) echo "再见！"; exit 0 ;;
            *) echo "无效选项"; sleep 1 ;;
        esac
        echo ""
        read -p "按 Enter 返回..."
    done
}

# ── 命令行分发 ──
case "$CMD" in
    start|stop|restart|status)
        ensure_venv
        exec "$VENV_PYTHON" "$ROOT/server_manager.py" "$CMD" "$@"
        ;;
    install)  cmd_install ;;
    check)    ensure_venv; cmd_check ;;
    "")       run_menu ;;
    *)
        echo "用法: $0 {start|stop|restart|status|install|check}  或无参数进入菜单"
        echo "  start  [--port PORT]  启动（默认 9176）"
        echo "  restart [--port PORT] 重启"
        exit 1
        ;;
esac
