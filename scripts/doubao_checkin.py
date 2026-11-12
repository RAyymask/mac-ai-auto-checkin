#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包电脑版「签到领额度」（纯标准库，无第三方依赖）。

参考来源（仅借鉴接口契约，不复制代码）：
  - hiclaw168-163/auto-signin-kit：docs/notes/NOTE-04-豆包签到接口逆向.md、
    domains/client_signin/apps/doubao_cn/{api,schema}.py
  - tututashu/doubao-auto-checkin：macOS 客户端 Cookie 解密链路（MIT）

!! 风控须知（务必先读）!!
  auto-signin-kit 于 2026-11-07 实测：活动页前端 SDK 的请求带 a_bogus /
  msToken / web_id / tea_uuid 等签名与设备指纹，裸 HTTP 缺这一层可能被判为
  异常流量；**连续发裸请求会让该会话被置为受限**，之后连在客户端手工点签到
  都会失败，重装客户端才能恢复。因此本脚本采取三道约束：

    1. 领取前先调用只读的 v3/detail，只有确认「今天还没签」才发写请求；
    2. 领取请求每次运行**恰好一次，绝不重试、绝不自动补发**；
    3. 只读查询失败时直接收手，不在状态不明的情况下继续打接口。

  ``--dry-run`` 只查状态、不发任何写请求，排查时优先用它。
  若返回 710010702「系统错误」，请先设 DOUBAO_DISABLE=1 停掉自动请求，
  再在豆包客户端手工签到，不要反复重跑本脚本。2026-11-13 本机实测：
  会话一旦被置为受限，客户端内点「立即签到」同样会返回
  「签到失败，请稍后重试」，此时需退出账号重登、必要时重装客户端才能恢复。

凭据（零配置）：~/Library/Application Support/Doubao/{Default,Profile *}/Cookies
  加密为客户端魔改的 Chromium v10：钥匙串密钥（base64 字符串本身）经
  PBKDF2-SHA1(saltysalt, 1003, 16B) 派生 AES-128-CBC 密钥，IV 为 16 个空格，
  明文去掉 PKCS7 填充后还需跳过客户端自加的 32 字节头。
  AES 解密调用 macOS 自带的 /usr/bin/openssl，因此不需要 pycryptodome。

用法
  python3 doubao_checkin.py --dry-run   # 只查状态（推荐先跑这个）
  python3 doubao_checkin.py             # 未签才领，最多一次写请求
  DOUBAO_COOKIE='sessionid=...; sid_tt=...' python3 doubao_checkin.py  # 手动凭据
"""

import argparse
import base64  # noqa: F401  （保留：便于将来切换到 base64 解码的密钥变体）
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import checkin_protocol as proto
except ImportError:  # 允许单独拷出来跑
    proto = None

APP = "Doubao"
HOME = Path.home()
ROOT = HOME / "Library" / "Application Support" / "Doubao"
KEYCHAIN_SERVICES = ("Doubao Browser Safe Storage", "Doubao Safe Storage")
REQUIRED_COOKIES = ("sessionid", "sid_tt", "uid_tt")
VALUE_PREFIX = 32

BASE_URL = "https://www.doubao.com"
COMMON_QUERY = ("version_code=20800&language=zh&device_platform=web"
                "&doubao_device_platform=web&aid=497858&real_aid=497858"
                "&pkg_type=release_version")
DETAIL_PATH = "/alice/ug/campaign/v3/detail/"
CHECKIN_PATH = "/alice/ug/campaign/landing/checkin/"
DEFAULT_CAMPAIGN = "pc_incentive_task_mvp_v3"
UA_VERSION = os.environ.get("DOUBAO_CLIENT_UA_VERSION", "2.33.3")
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 "
              "SamanthaDoubao/%s" % UA_VERSION)


def log(msg):
    sys.stderr.write("[Doubao] %s\n" % msg)


def finish(result, report, **extra):
    obj = {"app": APP, "result": result, "report": report}
    obj.update(extra)
    if proto is not None:
        proto.emit(obj)
    else:
        print(json.dumps(obj, ensure_ascii=False))
    return 0 if result in ("CLAIMED", "ALREADY", "DRY_RUN", "SKIP") else 1


# --------------------------------------------------------------------------
# 凭据：钥匙串密钥 + Cookie 库解密
# --------------------------------------------------------------------------

def keychain_keys():
    """返回所有可用的 (密钥材料, 来源说明) 候选；绝不打印密钥内容。

    不同客户端版本对钥匙串值的用法不同：当前版本直接把 base64 字符串作为
    PBKDF2 输入，标准 Chromium 则用 base64 解码后的 16 字节。两种都试，避免
    把版本差异误判成「登录态失效」。单个 service 超时不阻塞其余候选。
    """
    out = []
    for service in KEYCHAIN_SERVICES:
        try:
            r = subprocess.run(["security", "find-generic-password", "-w", "-s", service],
                               capture_output=True, timeout=6)
        except Exception:
            continue
        if r.returncode != 0 or not r.stdout.strip():
            continue
        raw = r.stdout.strip()
        out.append((raw, service + "（base64 字符串）"))
        try:
            decoded = base64.b64decode(raw)
            if decoded:
                out.append((decoded, service + "（解码后）"))
        except Exception:
            pass
    return out


def openssl_bin():
    return shutil.which("openssl") or "/usr/bin/openssl"


def make_aes_key(key_material):
    return hashlib.pbkdf2_hmac("sha1", key_material, b"saltysalt", 1003, dklen=16)


def decrypt_value(blob, aes_key, openssl):
    """解一条 v10 cookie；失败返回 None，绝不把密文残渣当明文。"""
    if not blob or not blob.startswith(b"v10"):
        return None
    cipher = blob[3:]
    if len(cipher) < 16 or len(cipher) % 16:
        return None
    try:
        r = subprocess.run(
            [openssl, "enc", "-d", "-aes-128-cbc", "-K", aes_key.hex(),
             "-iv", (b" " * 16).hex(), "-nopad"],
            input=cipher, capture_output=True, timeout=10)
        if r.returncode != 0:
            return None
        plain = r.stdout
    except Exception:
        return None
    pad = plain[-1] if plain else 0
    if 1 <= pad <= 16 and plain[-pad:] == bytes([pad]) * pad:
        plain = plain[:-pad]
    for candidate in (plain[VALUE_PREFIX:], plain):
        try:
            value = candidate.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if value and value.isprintable():
            return value
    return None


def candidate_dbs():
    """Default 优先，其余 Profile 按修改时间新者优先（新会话赢旧会话）。"""
    paths = [ROOT / "Default" / "Cookies"]
    try:
        profiles = sorted((p for p in ROOT.glob("Profile */Cookies") if p.is_file()),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        paths.extend(profiles)
    except OSError:
        pass
    return [p for p in paths if p.is_file()]


def read_cookies():
    """返回 (cookie_header, 诊断信息)。cookie 值绝不进入日志或结果。"""
    manual = os.environ.get("DOUBAO_COOKIE", "").strip()
    if manual:
        return manual, "来自环境变量 DOUBAO_COOKIE"

    dbs = candidate_dbs()
    if not dbs:
        return "", "未找到豆包客户端 Cookie 库（%s）；请安装并登录豆包电脑版" % ROOT
    candidates = keychain_keys()
    if not candidates:
        return "", ("读不到钥匙串密钥（%s）。请在 macOS「终端」里手动运行一次 "
                    "doubao_checkin.py --dry-run，弹窗时选「始终允许」；"
                    "无 GUI 会话的后台任务无法完成首次授权" %
                    " / ".join(KEYCHAIN_SERVICES))
    openssl = openssl_bin()

    # 先把所有候选库的密文读进内存，再逐个密钥试解，选解出条数最多的那个。
    rows_by_db = []
    tmp = Path(tempfile.gettempdir()) / ("wb-doubao-cookies-%d.db" % os.getpid())
    try:
        for db in dbs:
            try:
                shutil.copy(str(db), str(tmp))
                con = sqlite3.connect(str(tmp))
                try:
                    rows = con.execute(
                        "SELECT host_key, name, encrypted_value FROM cookies "
                        "WHERE host_key LIKE '%doubao%'").fetchall()
                finally:
                    con.close()
                rows_by_db.append(rows)
            except Exception:
                continue
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass

    best, source = {}, ""
    for key_material, label in candidates:
        aes_key = make_aes_key(key_material)
        merged = {}
        for rows in rows_by_db:
            # 同一库内域级 cookie（.doubao.com）优先于主机级，避免同名覆盖
            for prefer_dot in (True, False):
                for host, name, blob in rows:
                    if name in merged or host.startswith(".") != prefer_dot:
                        continue
                    value = decrypt_value(bytes(blob or b""), aes_key, openssl)
                    if value:
                        merged[name] = value
        if len(merged) > len(best):
            best, source = merged, label
        if all(n in merged for n in REQUIRED_COOKIES):
            break

    missing = [n for n in REQUIRED_COOKIES if n not in best]
    if missing:
        return "", ("登录态不完整（缺 %s，共解出 %d 条，密钥候选 %d 个）；"
                    "请打开豆包电脑版重新登录一次，或设置 DOUBAO_COOKIE"
                    % (",".join(missing), len(best), len(candidates)))
    header = "; ".join("%s=%s" % (n, v) for n, v in sorted(best.items()))
    return header, "来自客户端 Cookie 库（%d 条，%s）" % (len(best), source)


# --------------------------------------------------------------------------
# 请求
# --------------------------------------------------------------------------

def post(path, body, cookie_header, timeout=20):
    url = "%s%s?%s" % (BASE_URL, path, COMMON_QUERY)
    headers = {
        "Cookie": cookie_header,
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/pc/agent-explore",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
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
        return status, None, "响应不是 JSON"


def biz_error(status, payload):
    """把网关/业务错误翻译成人话，含风控提示。"""
    code = str((payload or {}).get("code") or "")
    msg = str((payload or {}).get("msg") or (payload or {}).get("message") or "")
    if status == 0:
        return "NO_AUTH", "网络异常：%s" % msg
    if status in (401, 403) or code.startswith("710012"):
        return "NO_AUTH", ("登录态已过期（code=%s）；请打开豆包电脑版重新登录，"
                          "退出客户端让 Cookie 落盘后重试" % (code or status))
    if code == "2":
        return "INACTIVE", ("活动不在期或已换季（campaign not found）；"
                           "请更新 DOUBAO_CAMPAIGN_CODE")
    if code == "710010702":
        return "ERROR", ("服务端返回 710010702 系统错误。多为裸请求缺少 "
                         "a_bogus 签名导致会话被置为受限，也可能是服务端故障。"
                         "**不要反复重跑本脚本**；先设 DOUBAO_DISABLE=1 停掉自动请求，"
                         "再在客户端手工签到。注意会话受限时客户端签到也可能提示"
                         "「签到失败，请稍后重试」，此时需退出重登/重装客户端恢复")
    return "ERROR", "请求失败 HTTP %s code=%s %s" % (status, code or "?", msg[:120])


def today_state(payload):
    """从 v3/detail 读今日是否已签；结构不认识返回 None（不猜）。"""
    tasks = ((payload or {}).get("data") or {}).get("tasks") or []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if task.get("campaign_code") == "daily_signin":
            daily = task.get("daily_checkin") or {}
            return bool(daily.get("checked_in_today")), daily
    return None, {}


def run(dry_run=False):
    campaign = os.environ.get("DOUBAO_CAMPAIGN_CODE", DEFAULT_CAMPAIGN).strip()
    cookie, diag = read_cookies()
    if not cookie:
        return finish("NO_AUTH", diag)

    # 1) 只读状态查询。失败就收手，绝不在状态不明时继续打接口。
    status, payload, err = post(DETAIL_PATH, {"campaign_group_code": campaign}, cookie)
    if status != 200 or not isinstance(payload, dict) or payload.get("code") != 0:
        result, msg = biz_error(status, payload if isinstance(payload, dict) else {"msg": err})
        return finish(result, "活动详情查询失败：%s" % msg)
    checked, daily = today_state(payload)
    if checked is True:
        amount = (daily.get("reward") or {}).get("reward_amount")
        return finish("ALREADY", "今日已签到 +%s 额度（连签 %s 天）"
                      % (amount if amount is not None else "?",
                         daily.get("continuous_days") or daily.get("streak_days") or "?"),
                      credits=amount, streak_days=daily.get("continuous_days"))
    if dry_run:
        note = "（活动面板结构未识别，依据服务端幂等保护）" if checked is None else ""
        return finish("DRY_RUN", "空跑：活动在期，今日未签；未发送领取请求%s" % note)

    # 2) 唯一一次写请求：幂等接口，不重试、不补发、事后不再复查。
    status, payload, err = post(CHECKIN_PATH, {"scene": campaign}, cookie)
    if status != 200 or not isinstance(payload, dict) or payload.get("code") != 0:
        result, msg = biz_error(status, payload if isinstance(payload, dict) else {"msg": err})
        return finish(result, "签到失败：%s" % msg)
    data = payload.get("data") or {}
    if data.get("idempotent"):
        return finish("ALREADY", "今日已签到（服务端返回幂等重复）",
                      credits=data.get("reward_amount"),
                      streak_days=data.get("continuous_days"))
    return finish("CLAIMED", "签到成功 +%s 额度（连签 %s 天）"
                  % (data.get("reward_amount", "?"), data.get("continuous_days", "?")),
                  credits=data.get("reward_amount"),
                  streak_days=data.get("continuous_days"))


def main():
    ap = argparse.ArgumentParser(description="豆包每日签到（纯 HTTP）")
    ap.add_argument("--dry-run", action="store_true", help="只查状态，不领取")
    ap.add_argument("--json", action="store_true", help="兼容参数：结果本就是结构化输出")
    args = ap.parse_args()
    try:
        return run(dry_run=args.dry_run)
    except Exception as exc:
        return finish("ERROR", "未预期异常：%s: %s" % (type(exc).__name__, exc))


if __name__ == "__main__":
    sys.exit(main())
