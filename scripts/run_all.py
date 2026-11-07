#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 助手每日一键自动签到编排层（WorkBuddy / Trae / Qoder）。

只负责调度、汇总与日志；凭据读取和 API 调用都在各子脚本内完成。

用法：
    run_all.py            正常执行，写 checkin.log 并发系统通知
    run_all.py --json     stdout 只输出一行 JSON 汇总，供 CI / 外部消费
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "checkin.log"
MAX_LOG_BYTES = 1024 * 1024
QUIET = False

try:
    import checkin_protocol as proto
except ImportError as exc:
    sys.stderr.write("缺少 checkin_protocol.py：%s\n" % exc)
    sys.exit(2)

ICONS = {
    proto.STATUS_OK: "✅",
    proto.STATUS_ALREADY: "✅",
    proto.STATUS_SKIP: "⏭️",
    proto.STATUS_WARN: "ℹ️",
    proto.STATUS_AUTH: "⚠️",
    proto.STATUS_FAIL: "❌",
}


def _rotate_log():
    """单文件轮转：超过 1 MB 时把旧日志挪到 checkin.log.1。"""
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_BYTES:
            backup = LOG_FILE.with_name(LOG_FILE.name + ".1")
            if backup.exists():
                backup.unlink()
            LOG_FILE.rename(backup)
    except Exception:
        pass


def log(msg):
    _rotate_log()
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        str(msg).replace("\n", " "))
    if not QUIET:
        print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _esc(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def send_notification(lines):
    """macOS 原生通知。

    AppleScript 不会把 \\n 解释成换行，旧版用 "\\n".join 会把字面反斜杠显示出来，
    这里改用分号拼接；引号做转义，避免消息里的双引号破坏脚本。
    """
    body = "; ".join(lines)
    script = 'display notification "%s" with title "%s" subtitle "%s"' % (
        _esc(body), _esc("每日签到助手"), _esc("AI 助手积分领取完毕"))
    try:
        res = subprocess.run(["osascript", "-e", script],
                             capture_output=True, timeout=5)
        if res.returncode != 0:
            log("  · 系统通知未送达（可在「系统设置 → 通知」检查权限）")
    except Exception as exc:
        log("  · 系统通知跳过：%s" % type(exc).__name__)


def _fail(app, result, msg):
    return {"app": app, "status": proto.STATUS_FAIL, "result": result, "msg": msg}


def _run(app, script, *args, timeout=60, env=None):
    path = BASE_DIR / script
    if not path.exists():
        return {"app": app, "status": proto.STATUS_SKIP, "result": "SKIP",
                "msg": "未找到 %s" % script}
    try:
        res = subprocess.run([sys.executable, str(path), *args],
                             capture_output=True, text=True, timeout=timeout, env=env)
        out = proto.resolve(app, res.stdout, res.stderr)
        if out["status"] == proto.STATUS_FAIL and out["msg"] == "执行无有效返回":
            out["msg"] = "执行无有效返回，请查看 %s" % script.replace(".py", ".log")
        return out
    except subprocess.TimeoutExpired:
        return _fail(app, "TIMEOUT", "%s 执行超过 %d 秒" % (script, timeout))
    except Exception as exc:
        return _fail(app, "ERROR", "%s 异常：%s" % (script, exc))


def _report(app, r):
    mark = "✓" if r["status"] in (proto.STATUS_OK, proto.STATUS_ALREADY) else ICONS.get(r["status"], "·")
    log("  %s [%s] %s" % (mark, app, r["msg"]))


def checkin_workbuddy():
    log("▶ [WorkBuddy] 开始执行签到...")
    r = _run("WorkBuddy", "signin.py", "auto", timeout=60)
    _report("WorkBuddy", r)
    return r


def checkin_trae():
    log("▶ [Trae] 开始执行签到...")
    token_helper = BASE_DIR / "trae_get_token.py"
    checkin_script = BASE_DIR / "trae_checkin.py"
    if not (token_helper.exists() and checkin_script.exists()):
        r = {"app": "Trae", "status": proto.STATUS_SKIP, "result": "SKIP",
             "msg": "未找到 Trae 脚本"}
        _report("Trae", r)
        return r
    try:
        import trae_get_token
        accounts = []
        for p in trae_get_token.candidate_paths():
            acc = trae_get_token.extract(p)
            if acc:
                acc["realDeviceId"] = trae_get_token.device_id_in(p)
                acc["name"] = acc.get("nickname") or "UID_%s" % acc.get("uid")
                accounts.append(acc)
                break
        if not accounts:
            r = _fail("Trae", "NO_AUTH", "未在本地发现 Trae 客户端登录凭据")
        else:
            env = dict(os.environ, TRAE_ACCOUNTS=json.dumps(accounts), TRAE_JITTER="0")
            r = _run("Trae", "trae_checkin.py", timeout=60, env=env)
    except Exception as exc:
        r = _fail("Trae", "ERROR", "异常：%s" % exc)
    _report("Trae", r)
    return r


def checkin_qoder():
    log("▶ [Qoder] 开始执行签到...")
    r = _run("Qoder", "qoder_signin.py", "auto", timeout=25)
    _report("Qoder", r)
    return r


def main():
    global QUIET
    as_json = "--json" in sys.argv[1:]
    QUIET = as_json

    log("=" * 55)
    log("🚀 启动 AI 办公助手每日自动签到")
    results = [checkin_workbuddy(), checkin_trae(), checkin_qoder()]
    log("-" * 55)
    summary = []
    for r in results:
        text = "%s %s: %s" % (ICONS.get(r["status"], "·"), r["app"], r["msg"])
        summary.append(text)
        log(text)
    log("=" * 55 + "\n")

    failed = [r for r in results if r["status"] == proto.STATUS_FAIL]
    if as_json:
        payload = {
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "ok": not failed,
            "results": [{k: v for k, v in r.items() if k != "raw"} for r in results],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        send_notification(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
