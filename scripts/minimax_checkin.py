#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MiniMax Code 每日签到（纯标准库，无第三方依赖）。

参考来源（仅借鉴协议，不复制代码）：
  - MiniMax-AI/minimax-code（官方 TUI）
      packages/tui/src/checkin/http-gateway.ts
      packages/tui/src/runtime/public-gateway.ts
      packages/shared/src/daily-signin.ts
  - welldo/QinglongMy/minimax_checkin.py（token 续期与诊断思路）

协议要点
  CN 域名  https://agent.minimaxi.com      国际域名 https://agent.minimax.io
  状态查询 GET  /minimax-cloud/api/v1/signin/status
  领取     POST /minimax-cloud/api/v1/signin/claim   body {}
  鉴权     Authorization: Bearer <accessToken>，query 里必须带 user_id=realUserID
  签名头   x-timestamp / x-signature / yy 均为 md5，详见 build_request()
  幂等     status 面板中 is_today && status==3 表示今日已领；
           claim 的 claim_result 1=新领取 2=今日已领

凭据（零配置，按优先级）
  1. 环境变量 MINIMAX_ACCESS_TOKEN / MINIMAX_USER_ID / MINIMAX_REGION
  2. ~/.minimax/auth/prod/<region>/mcode-public/auth.json 的 records.*.accessToken
  3. ~/Library/Application Support/MiniMax/minimax-agent-cn-config.json
     的 sharedUser.realUserID

用法
  python3 minimax_checkin.py                # 查询状态，未签才领取
  python3 minimax_checkin.py --dry-run      # 只查状态，绝不发写请求
  python3 minimax_checkin.py --json         # 结果同时以 JSON 打印
"""

import argparse
import hashlib
import json
import os
import plistlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path

try:
    import checkin_protocol as proto
except ImportError:  # 允许单独拷出来跑
    proto = None

APP = "MiniMax"
HOME = Path.home()
ORIGINS = {"cn": "https://agent.minimaxi.com", "en": "https://agent.minimax.io"}
STATUS_PATH = "/minimax-cloud/api/v1/signin/status"
CLAIM_PATH = "/minimax-cloud/api/v1/signin/claim"
SIGNATURE_SALT = "I*7Cf%WZ#S&%1RlZJ&C2"
AUTH_ROOT = HOME / ".minimax" / "auth" / "prod"
CLIENT_CONFIG = (HOME / "Library" / "Application Support" / "MiniMax" /
                 "minimax-agent-cn-config.json")
APP_PLIST = Path("/Applications/MiniMax Code.app/Contents/Info.plist")

# 官方 daily-signin.ts 的枚举
DAY_UPCOMING, DAY_CLAIMABLE, DAY_CLAIMED, DAY_DISABLED = 1, 2, 3, 4
CLAIM_NEW, CLAIM_ALREADY = 1, 2


def log(msg):
    sys.stderr.write("[MiniMax] %s\n" % msg)


def finish(result, report, **extra):
    obj = {"app": APP, "result": result, "report": report}
    obj.update(extra)
    if proto is not None:
        proto.emit(obj)
    else:
        print(json.dumps(obj, ensure_ascii=False))
    return 0 if result in ("CLAIMED", "ALREADY", "DRY_RUN", "SKIP") else 1


# --------------------------------------------------------------------------
# 凭据
# --------------------------------------------------------------------------

def app_version():
    """尽量取客户端版本号；取不到用空串（官方 TUI 允许空值）。"""
    try:
        with open(APP_PLIST, "rb") as f:
            return str(plistlib.load(f).get("CFBundleShortVersionString") or "")
    except Exception:
        return ""


def read_client_config():
    try:
        with open(CLIENT_CONFIG, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data


def read_auth_files(region):
    """返回 (token, expires_at_ms, region)。优先指定 region，选最晚过期的记录。"""
    if not AUTH_ROOT.is_dir():
        return "", 0, region
    candidates = sorted(AUTH_ROOT.glob("*/mcode-public/auth.json"),
                        key=lambda p: (p.parent.parent.name != region, str(p)))
    best = ("", 0, region)
    for path in candidates:
        found_region = path.parent.parent.name
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for rec in (data.get("records") or {}).values():
            if not isinstance(rec, dict):
                continue
            token = str(rec.get("accessToken") or "").strip()
            if not token:
                continue
            try:
                exp = int(rec.get("expiresAtMs") or 0)
            except (TypeError, ValueError):
                exp = 0
            if exp > best[1]:
                best = (token, exp, found_region)
    return best


def load_credentials():
    token = os.environ.get("MINIMAX_ACCESS_TOKEN", "").strip().strip('"').strip("'")
    user_id = os.environ.get("MINIMAX_USER_ID", "").strip()
    region = os.environ.get("MINIMAX_REGION", "").strip().lower() or "cn"
    exp = 0
    if not token:
        token, exp, found = read_auth_files(region)
        if token:
            region = found or region
    cfg = read_client_config()
    if not user_id:
        shared = cfg.get("sharedUser") or {}
        user = cfg.get("user") or {}
        user_id = str(shared.get("realUserID") or user.get("realUserID") or "").strip()
    if region not in ORIGINS:
        region = "cn"
    return {"token": token, "user_id": user_id, "region": region, "expires_at_ms": exp}


# --------------------------------------------------------------------------
# 请求签名（对齐官方 createPublicGatewayRequest）
# --------------------------------------------------------------------------

def encode_uri_component(value):
    """忠实复刻 JS encodeURIComponent：只放行 A-Za-z0-9 - _ . ! ~ * ' ( )。"""
    return re.sub(r"([^A-Za-z0-9\-_.!~*'()])",
                  lambda m: "%%%02X" % ord(m.group(1)), value)


def md5_hex(value):
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def build_request(origin, path, cred, method, body_str=None):
    now_ms = int(time.time() * 1000)
    second = now_ms // 1000
    tz = time.altzone if (time.daylight and time.localtime().tm_isdst) else time.timezone
    params = OrderedDict([
        ("device_platform", "web"),
        ("biz_id", "3"),
        ("app_id", "3001"),
        ("version_code", "22201"),
        ("is_desktop", "1"),
        ("desktop_version", app_version()),
        ("unix", str(now_ms)),
        ("timezone_offset", str(-tz)),
        ("sys_language", "zh" if cred["region"] == "cn" else "en"),
        ("lang", "zh" if cred["region"] == "cn" else "en"),
        ("device_id", "0"),
        ("os_name", "darwin"),
        ("browser_name", "mcode"),
        ("user_id", cred["user_id"]),
        ("client", "mcode"),
    ])
    query = urllib.parse.urlencode(params)
    path_with_search = "%s?%s" % (path, query)

    signature_body = body_str or ""
    yy_body = body_str or "{}"
    yy = md5_hex(encode_uri_component(path_with_search) + "_" + yy_body
                 + md5_hex(str(now_ms)) + "ooui")
    x_signature = md5_hex("%d%s%s" % (second, SIGNATURE_SALT, signature_body))

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "MiniMaxCode",
        "Authorization": "Bearer %s" % cred["token"],
        "yy": yy,
        "x-timestamp": str(second),
        "x-signature": x_signature,
    }
    url = "%s%s?%s" % (origin, path, query)
    return url, headers, (body_str.encode("utf-8") if body_str else None)


def http_json(url, headers, data, method, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except Exception as exc:
        return 0, None, "%s: %s" % (type(exc).__name__, exc)
    try:
        return status, json.loads(raw.decode("utf-8", "replace")), ""
    except Exception:
        return status, None, "响应不是 JSON（前 120 字符已省略，不含凭据）"


def api_call(cred, path, method, body, timeout=20):
    origin = ORIGINS[cred["region"]]
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else None
    url, headers, data = build_request(origin, path, cred, method, body_str)
    return http_json(url, headers, data, method, timeout)


def unwrap(body):
    """取官方网关的 data；失败返回 (None, 错误原因)。"""
    if not isinstance(body, dict):
        return None, "响应结构异常"
    base = body.get("base_resp") or {}
    code = base.get("status_code") if isinstance(base, dict) else None
    if isinstance(code, int) and code != 0:
        return None, "%s (code=%s)" % (base.get("status_msg") or "网关返回失败", code)
    data = body.get("data")
    if data is None:
        return None, "响应缺少 data"
    return data, ""


# --------------------------------------------------------------------------
# 业务
# --------------------------------------------------------------------------

def panel_today(panel):
    days = (panel or {}).get("days") or []
    return next((d for d in days if isinstance(d, dict) and d.get("is_today")), None)


def streak_days(panel):
    days = sorted((d for d in ((panel or {}).get("days") or [])
                   if isinstance(d, dict)), key=lambda d: d.get("day_no") or 0)
    today = next((i for i, d in enumerate(days) if d.get("is_today")), -1)
    if today < 0:
        return 0
    state = days[today].get("status")
    index = today if state == DAY_CLAIMED else (today - 1 if state == DAY_CLAIMABLE else -1)
    count = 0
    while index >= 0 and days[index].get("status") == DAY_CLAIMED:
        count += 1
        index -= 1
    return count


def run(dry_run=False):
    cred = load_credentials()
    if not cred["token"]:
        return finish("NO_AUTH", "未找到 MiniMax Code 登录态；请在客户端登录一次，"
                      "或设置 MINIMAX_ACCESS_TOKEN / MINIMAX_USER_ID")
    if not cred["user_id"]:
        return finish("NO_AUTH", "缺少 realUserID（user_id），签到接口会误报 401；"
                      "请设置 MINIMAX_USER_ID 或登录客户端后重试")
    if cred["expires_at_ms"] and cred["expires_at_ms"] < int(time.time() * 1000):
        return finish("NO_AUTH", "accessToken 已过期；请在 MiniMax Code 客户端重新登录一次")

    status, body, err = api_call(cred, STATUS_PATH, "GET", None)
    if status == 0:
        return finish("ERROR", "网络异常：%s" % err)
    if status in (401, 403):
        return finish("NO_AUTH", "鉴权失败 HTTP %d：token 失效或 user_id 不匹配；"
                      "请重新登录 MiniMax Code 客户端" % status)
    if status != 200:
        return finish("ERROR", "状态查询失败 HTTP %d" % status)
    panel, why = unwrap(body)
    if panel is None:
        return finish("ERROR", "状态查询失败：%s" % why)

    today = panel_today(panel)
    streak = streak_days(panel)
    if today is None:
        return finish("WARN", "7 日面板未标记今天，跳过领取（接口可能已改版）",
                      streak_days=streak)
    day_state = today.get("status")
    points_today = today.get("points")
    if day_state == DAY_CLAIMED:
        return finish("ALREADY", "今日已签到（第 %s 天，+%s 积分）"
                      % (today.get("day_no"), points_today),
                      streak_days=streak, points=points_today)
    if dry_run:
        return finish("DRY_RUN", "空跑：今天可领（第 %s 天，+%s 积分），未发送领取请求"
                      % (today.get("day_no"), points_today),
                      streak_days=streak, points=points_today)
    if day_state != DAY_CLAIMABLE:
        return finish("SKIP", "今天不可领（面板状态 %s，非可领状态），未发送领取请求"
                      % day_state, streak_days=streak)

    # 只有面板明确「今天可领」才发唯一一次写请求，且绝不重试。
    status, body, err = api_call(cred, CLAIM_PATH, "POST", {})
    if status == 0:
        return finish("ERROR", "领取请求网络异常（不自动重试，避免重复领取）：%s" % err)
    if status in (401, 403):
        return finish("NO_AUTH", "领取时鉴权失败 HTTP %d；请重新登录客户端" % status)
    if status != 200:
        return finish("ERROR", "领取失败 HTTP %d（不自动重试）" % status)
    data, why = unwrap(body)
    if data is None:
        return finish("ERROR", "领取失败：%s" % why)
    result_code = data.get("claim_result")
    points = data.get("points")
    if result_code == CLAIM_ALREADY:
        return finish("ALREADY", "今日已签到（服务端返回重复领取）",
                      streak_days=streak, points=points)
    if result_code == CLAIM_NEW:
        return finish("CLAIMED", "签到成功 +%s 积分（第 %s 天）"
                      % (points, data.get("day_no")),
                      streak_days=streak, points=points)
    return finish("ERROR", "领取返回未知 claim_result=%s（未重复发起）" % result_code)


def main():
    ap = argparse.ArgumentParser(description="MiniMax Code 每日签到")
    ap.add_argument("--dry-run", action="store_true", help="只查状态，不领取")
    ap.add_argument("--json", action="store_true", help="兼容参数：结果本就是结构化输出")
    args = ap.parse_args()
    try:
        return run(dry_run=args.dry_run)
    except Exception as exc:
        return finish("ERROR", "未预期异常：%s: %s" % (type(exc).__name__, exc))


if __name__ == "__main__":
    sys.exit(main())
