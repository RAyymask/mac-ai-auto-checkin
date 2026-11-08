#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""签到结果统一协议（编排层归一化）。

设计取舍：三个子脚本来自不同上游项目，直接改它们的 stdout 格式会破坏既有
用户与上游兼容性。因此这里定义一条可选的机器可读结果行::

    __CHECKIN__ {"app": "...", "result": "CLAIMED", ...}

子脚本可以继续保留原有输出；``extract()`` 优先读机器可读行，读不到时再
解析它们原有的 JSON / 文本输出。所有状态集中在下面的 STATUS_* 常量。
"""

import json

PREFIX = "__CHECKIN__ "

STATUS_OK = "OK"
STATUS_ALREADY = "ALREADY"
STATUS_SKIP = "SKIP"
STATUS_WARN = "WARN"
STATUS_AUTH = "AUTH_NEEDED"
STATUS_FAIL = "FAIL"

_OK_RESULTS = ("CLAIMED", "OK", "SUCCESS", "SIGNED")
_ALREADY_RESULTS = ("ALREADY", "INACTIVE", "DRY_RUN", "SKIP")
_AUTH_RESULTS = ("NO_AUTH", "NO_SESSION", "AUTH_ERROR", "AUTH_REJECTED")
_FAIL_RESULTS = ("ERROR", "UNKNOWN", "NETWORK", "TIMEOUT", "FAIL", "FORBIDDEN")


def emit(result):
    """供子脚本打印一行机器可读结果；保证不抛异常。"""
    try:
        print(PREFIX + json.dumps(result, ensure_ascii=False, default=str), flush=True)
    except Exception:
        pass


def parse_marker(stdout):
    """取最后一条机器可读结果行（中间的进度行会被后续结果覆盖）。"""
    found = None
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith(PREFIX):
            continue
        try:
            obj = json.loads(line[len(PREFIX):])
        except Exception:
            continue
        if isinstance(obj, dict):
            found = obj
    return found


def parse_legacy_json(stdout):
    """解析子脚本原有的 JSON 输出，只认带 result 的最终结果行。

    signin.py 在流程中还会打印 {"step": "status", ...} 之类的中间行，
    旧版 run_all.py 取第一行 JSON 就返回，会把中间行误判成最终结果。
    这里收集所有带 result 的行并取最后一行。
    """
    candidates = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict) and "result" in obj:
            candidates.append(obj)
    return candidates[-1] if candidates else None


def parse_legacy_text(app, stdout):
    """兜底解析纯文本输出（目前只有 Trae 走这条路径）。"""
    if app != "Trae":
        return None
    out = stdout or ""
    if not out.strip():
        return None
    if "签到成功" in out or "今日已签到" in out or "已签到" in out:
        balance = ""
        for line in out.splitlines():
            if "当前余额" in line:
                balance = line.split("当前余额")[-1].strip()
                break
        return {"app": app, "result": "CLAIMED",
                "report": "签到成功 (+100积分)" + ("，当前额度 %s" % balance if balance else ""),
                "credits": balance}
    return {"app": app, "result": "ERROR", "report": out.strip()[-300:]}


def extract(app, stdout, stderr=""):
    """按优先级取出子脚本的结果对象；取不到返回 None。"""
    obj = parse_marker(stdout)
    if obj is None:
        obj = parse_legacy_json(stdout)
    if obj is None:
        obj = parse_legacy_text(app, stdout)
    return obj


def _message(app, status, res, report, obj):
    if app == "WorkBuddy":
        streak = obj.get("streak_days")
        total = obj.get("total_credits")
        gain = obj.get("today_credit", 100)
        if status in (STATUS_OK, STATUS_ALREADY) and streak is not None and total is not None:
            head = "签到成功" if status == STATUS_OK else "今日已签"
            return "%s (+%s积分)，连签 %s 天，累计 %s" % (head, gain, streak, total)
    if app == "Qoder":
        if status == STATUS_OK:
            return "成功领取 100 Credits"
        if status == STATUS_ALREADY:
            return "已领今日 100 Credits"
        if status == STATUS_AUTH:
            return "需钥匙串授权（终端运行一次即可激活）"
    if app == "Trae" and status in (STATUS_OK, STATUS_ALREADY):
        head = "签到成功" if status == STATUS_OK else "今日已完成"
        balance = obj.get("credits") or ""
        return "%s (+100积分)%s" % (head, ("，当前额度 %s" % balance) if balance else "")
    if app in ("MiniMax", "Doubao") and status in (STATUS_OK, STATUS_ALREADY):
        return report or ("签到成功" if status == STATUS_OK else "今日已签")
    return report or res or "无有效返回"


def normalize(app, obj):
    """把子脚本结果映射为统一的 {app,status,result,msg}。"""
    obj = dict(obj or {})
    res = str(obj.get("result") or obj.get("status") or "").upper()
    report = str(obj.get("report") or obj.get("msg") or obj.get("detail") or "").strip()
    if res in _OK_RESULTS:
        status = STATUS_OK
    elif res in _ALREADY_RESULTS:
        status = STATUS_ALREADY
    elif res in _AUTH_RESULTS:
        status = STATUS_AUTH
    elif res in _FAIL_RESULTS:
        status = STATUS_FAIL
    else:
        status = STATUS_WARN
    return {"app": app, "status": status, "result": res,
            "msg": _message(app, status, res, report, obj), "raw": obj}


def resolve(app, stdout, stderr=""):
    """一步到位：解析 + 归一化；完全无输出时给出可排障的 FAIL。"""
    obj = extract(app, stdout, stderr)
    if obj is None:
        detail = (stderr or "").strip()[-300:] or "执行无有效返回"
        return {"app": app, "status": STATUS_FAIL, "result": "", "msg": detail}
    return normalize(app, obj)
