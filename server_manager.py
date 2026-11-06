#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server_manager.py — Blog Editor 的 server 生命周期管理
  - start / stop / restart / status
  - PID 文件管理
  - 日志输出
  - 独立 CLI 入口:  python3 server_manager.py start [--port N]
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PID_FILE = ROOT / '.server.pid'
LOG_FILE = ROOT / '.server.log'
DEFAULT_PORT = 9176


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _get_pid() -> int | None:
    if not PID_FILE.is_file():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return None
    return pid


def _is_port_available(port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', port))
        s.close()
        return True
    except OSError:
        return False


def cmd_start(port: int = DEFAULT_PORT) -> int:
    pid = _get_pid()
    if pid and _pid_is_running(pid):
        print(f'server 已在运行 (PID {pid}, port {port})')
        return 0

    print(f'启动 Blog Editor (port {port}) ...')
    cmd = [sys.executable, str(ROOT / 'server.py'), '--port', str(port)]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=open(LOG_FILE, 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as e:
        print(f'✗ 启动失败: {e}')
        return 1

    PID_FILE.write_text(str(proc.pid))
    # 等一下确认进程没秒退
    time.sleep(1)
    if not _pid_is_running(proc.pid):
        print('✗ 启动失败，日志:')
        print(LOG_FILE.read_text())
        PID_FILE.unlink(missing_ok=True)
        return 1

    print(f'✓ 已启动: PID {proc.pid}')
    print(f'  http://127.0.0.1:{port}/')
    print(f'  日志: {LOG_FILE}')
    return 0


def cmd_stop() -> int:
    pid = _get_pid()
    if not pid:
        print('server 未运行')
        return 0
    if not _pid_is_running(pid):
        PID_FILE.unlink(missing_ok=True)
        print('server 未运行 (pid 文件已清理)')
        return 0

    print(f'停止 server (PID {pid}) ...')
    os.kill(pid, signal.SIGTERM)
    # 最多等 3 秒
    waited = 0
    while _pid_is_running(pid) and waited < 3:
        time.sleep(1); waited += 1
    if _pid_is_running(pid):
        print('  强制终止...')
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.2)
    PID_FILE.unlink(missing_ok=True)
    print('✓ 已停止')
    return 0


def cmd_restart(port: int = DEFAULT_PORT) -> int:
    cmd_stop()
    # SO_REUSEADDR 让 server.py 能直接 bind TIME_WAIT 端口，无需等待
    return cmd_start(port)


def cmd_status() -> int:
    pid = _get_pid()
    if pid and _pid_is_running(pid):
        import subprocess as sp
        out = sp.run(['ps', '-p', str(pid), '-o', 'args='], capture_output=True, text=True).stdout.strip()
        print(f'✓ 运行中  PID={pid}')
        if out:
            print(f'  {out}')
        return 0
    else:
        if PID_FILE.is_file():
            PID_FILE.unlink()
        print('✗ 未运行')
        return 1


def main():
    ap = argparse.ArgumentParser(description='Blog Editor server manager')
    ap.add_argument('action', choices=['start', 'stop', 'restart', 'status'], nargs='?', default='start')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    args = ap.parse_args()

    if args.action == 'start':
        sys.exit(cmd_start(args.port))
    elif args.action == 'stop':
        sys.exit(cmd_stop())
    elif args.action == 'restart':
        sys.exit(cmd_restart(args.port))
    elif args.action == 'status':
        sys.exit(cmd_status())


if __name__ == '__main__':
    main()
