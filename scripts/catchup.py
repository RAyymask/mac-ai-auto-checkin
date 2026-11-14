#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开机 / 登录后的补签守卫（配套 com.user.ai-daily-checkin.catchup.plist）。

为什么需要
  launchd 的 StartCalendarInterval 只在系统运行时触发；关机期间错过的
  10:05 / 15:05 / 20:05 不会被补跑。2026-11-14 实测：11-13 23:41 关机、
  11-14 15:32 才登录，当天前两轮全部漏掉，直到人工补跑才签到。

为什么单独一个 LaunchAgent
  同一个 plist 的 ProgramArguments 无法区分「RunAtLoad 启动」与「日历触发」。
  若把守卫塞进 run_all.py，每天后两轮会被误判成重复而跳过，反而丢掉补签
  机会。独立服务只在加载瞬间运行一次，日历三轮完全不受影响。

流程
  1. 等待网络就绪（默认最多 30 秒，避免开机瞬间网络尚未连上）
  2. 读 checkin.log，统计当天「启动标记 → 结束分隔符」的完整轮次
  3. 已有完整轮次 -> 只写一行日志，零网络请求退出
  4. 否则调用 run_all.py（继承环境变量，包括 DOUBAO_DISABLE=1）

用法
  python3 catchup.py              # 正常执行
  python3 catchup.py --dry-run    # 只报告决定，不联网、不调用 run_all.py
  python3 catchup.py --force      # 忽略当天守卫，强制补跑（排查用）

环境变量
  AUTO_CHECKIN_CATCHUP_NETWORK_WAIT  网络等待秒数，0 表示不等待（默认 30）
  AUTO_CHECKIN_CATCHUP_HOST          网络探测主机（默认 www.apple.com）
  AUTO_CHECKIN_CATCHUP_FORCE=1       等价于 --force
"""

import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "checkin.log"
RUN_ALL = BASE_DIR / "run_all.py"

START_MARK = "🚀 启动 AI 办公助手每日自动签到"
END_MARK = "=" * 55
DEFAULT_WAIT_SEC = 30
DEFAULT_HOST = "www.apple.com"
RUN_TIMEOUT_SEC = 600


def log(msg):
    """写 checkin.log（与 run_all.py 同格式），但不写轮次标记，避免自干扰。"""
    line = "[%s] [Catchup] %s" % (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        str(msg).replace("\n", " "))
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def wait_for_network(seconds, host):
    """TCP 探测目标主机 443 端口；超时也继续，交由各平台脚本自己报错。"""
    if seconds <= 0:
        return True, "已跳过网络等待"
    deadline = time.monotonic() + seconds
    tries = 0
    while True:
        tries += 1
        try:
            with socket.create_connection((host, 443), timeout=3):
                return True, "网络就绪（第 %d 次探测 %s:443）" % (tries, host)
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return False, "%d 秒内 %s:443 未就绪，仍尝试一次签到" % (seconds, host)
        time.sleep(2)


def complete_rounds_today(today):
    """统计当天完整轮次：START_MARK 之后出现 END_MARK 才算一轮。

    run_all.py 每轮的结构是「====(开头) / 🚀 启动 / ... / ---- / 汇总 / ====(结尾)」。
    半途崩溃或仍在执行中的轮次没有结尾分隔符，不会被误判成已完成。
    """
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return 0
    prefix = "[" + today
    started = False
    rounds = 0
    for line in lines:
        if not line.startswith(prefix):
            started = False
            continue
        if START_MARK in line:
            started = True
        elif started and END_MARK in line:
            rounds += 1
            started = False
    return rounds


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    force = "--force" in args or os.environ.get("AUTO_CHECKIN_CATCHUP_FORCE") == "1"
    today = datetime.now().strftime("%Y-%m-%d")
    rounds = complete_rounds_today(today)
    should_run = (rounds == 0) or force

    if dry_run:
        print("[Catchup] dry-run：今日完整轮次=%d；决定=%s；不联网、不调用 run_all.py"
              % (rounds, "补跑一轮" if should_run else "跳过"))
        return 0

    if not should_run:
        log("今日已有 %d 轮完整签到，无需补跑（零网络请求）" % rounds)
        return 0

    log("今日尚无完整签到轮次%s，开始补跑" % ("（--force）" if force else ""))
    wait_sec = _env_int("AUTO_CHECKIN_CATCHUP_NETWORK_WAIT", DEFAULT_WAIT_SEC)
    host = os.environ.get("AUTO_CHECKIN_CATCHUP_HOST") or DEFAULT_HOST
    ok, note = wait_for_network(wait_sec, host)
    log(note)

    if not RUN_ALL.is_file():
        log("未找到 run_all.py，放弃补跑")
        return 1
    try:
        res = subprocess.run([sys.executable, str(RUN_ALL)], timeout=RUN_TIMEOUT_SEC)
        rc = res.returncode
    except subprocess.TimeoutExpired:
        log("run_all.py 超过 %d 秒，已终止" % RUN_TIMEOUT_SEC)
        return 1
    except Exception as exc:
        log("调用 run_all.py 失败：%s" % type(exc).__name__)
        return 1
    log("补跑结束（run_all.py 退出码 %d；网络等待%s）"
        % (rc, "成功" if ok else "超时"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
