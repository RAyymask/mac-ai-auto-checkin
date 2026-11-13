#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MiniMax Code 每日签到（纯标准库，无第三方依赖）。

参考来源（仅借鉴协议，不复制代码）：
  - MiniMax-AI/minimax-code（官方 TUI）
      packages/tui/src/checkin/http-gateway.ts
      packages/tui/src/runtime/public-gateway.ts
      packages/shared/src/daily-signin.ts
  - welldo/QinglongMy/minimax_checkin.py（国际区 renewal 与诊断思路）
  - VICqiufeeng/dsh-minimax-connect（CN 区 OAuth2 refresh grant 实测契约）

协议要点
  CN 域名  https://agent.minimaxi.com      国际域名 https://agent.minimax.io
  续期     POST /v1/api/user/renewal  body {}  -> data.token（仅国际区 JWT 体系）
  状态查询 GET  /minimax-cloud/api/v1/signin/status
  领取     POST /minimax-cloud/api/v1/signin/claim   body {}
  鉴权     Authorization: Bearer <accessToken>，query 里必须带 user_id=realUserID
  签名头   x-timestamp / x-signature / yy 均为 md5，详见 build_request()
  幂等     status 面板中 is_today && status==3 表示今日已领；
           claim 的 claim_result 1=新领取 2=今日已领

凭据体系（2026-11-13 查证，两套协议不要混用）
  CN 区桌面端是 OAuth2：auth.json 里同时有 accessToken(mmoat_) 与
  refreshToken(mmort_)，都是 60 字符 opaque token（不是 JWT）。真实续期是
  POST https://account.minimax.cn/oauth2/token，
  grant_type=refresh_token / client_id=mcode-public / audience=agent-backend；
  refresh_token 单次使用且每次轮换，必须原子回写 auth.json + auth-state.json
  并递增 generation，否则客户端会把自己的新 token 判成「已登出」。
  本项目刻意不接管这一步：它要改客户端登录态，写坏会锁死账号。

  /v1/api/user/renewal 属于另一套（旧版/国际区）协议：Windows 桌面端
  minimax-agent-config.json 里的 HS256 JWT + agent.minimax.io + `token:` 头，
  返回 data.token 新 JWT（参考 welldo/QinglongMy）。把 CN 的 mmoat_ 塞进
  这个端点会恒定 401「登陆失败」，与 token 是否过期无关。

  因此 **CN 区默认不发 renewal**，直接拿客户端 auth.json 的 accessToken 签到，
  token 由客户端启动时自行刷新（本机实测约 12 小时有效期）。国际区默认保留
  renewal；MINIMAX_RENEW=1/0 可强制覆盖，--renew 用于显式探测。
  续期成功得到的新 token 只写 .minimax_token.json（0600），绝不回写客户端。

自动保持登录态（2026-11-13 新增）
  CN 区签到前读 auth.json 的 expiresAtMs：剩余不足 3 小时或已过期时，
  自行执行 /usr/bin/open -a "MiniMax Code" 启动客户端，轮询最多 20 秒等它
  刷新 auth.json，再重新读凭据签到。每天 10:05 那轮自动启动一次即可覆盖
  当天 10:05 / 15:05 / 20:05 三轮，不会再出现下午 401。
  * 只启动、不 quit / 重启正在运行的客户端，绝不改写客户端登录态。
  * --dry-run 与 --renew 保持零副作用，不启动客户端。
  * env 注入凭据 / 国际区 renewal 缓存为首选时不启动（不需要 GUI）。
  * MINIMAX_NO_LAUNCH=1 完全停用；MINIMAX_LAUNCH_MARGIN_MIN 调阈值
    （默认 180 分钟，仅用于排查）。
  * 客户端本就已运行且未刷新时，20 秒后记日志并沿用旧 token 继续签到，
    不会为了刷新而杀掉用户正在使用的客户端。

凭据（零配置，按优先级）
  1. 环境变量 MINIMAX_ACCESS_TOKEN / MINIMAX_USER_ID / MINIMAX_REGION
  2. 本项目续期缓存 .minimax_token.json（7 天内有效）
  3. ~/.minimax/auth/prod/<region>/mcode-public/auth.json 的 records.*.accessToken
  realUserID 取自 ~/Library/Application Support/MiniMax/
              minimax-agent-cn-config.json 的 sharedUser.realUserID

用法
  python3 minimax_checkin.py                # CN 区：直接查状态，未签才领取（不发 renewal）
  python3 minimax_checkin.py --renew        # 显式探测续期端点，不签到（CN 区预期 401）
  python3 minimax_checkin.py --dry-run      # 只查状态，不发任何写请求（含续期）
  python3 minimax_checkin.py --no-renew     # 跳过续期（CN 区默认已是跳过）
  MINIMAX_RENEW=1 python3 minimax_checkin.py   # 强制启用 renewal（国际区默认开启）
  MINIMAX_NO_LAUNCH=1 python3 minimax_checkin.py  # 不自动启动客户端
  python3 minimax_checkin.py --json         # 结果同时以 JSON 打印
"""

import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
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
BASE_DIR = Path(__file__).resolve().parent
ORIGINS = {"cn": "https://agent.minimaxi.com", "en": "https://agent.minimax.io"}
RENEW_PATH = "/v1/api/user/renewal"
STATUS_PATH = "/minimax-cloud/api/v1/signin/status"
CLAIM_PATH = "/minimax-cloud/api/v1/signin/claim"
SIGNATURE_SALT = "I*7Cf%WZ#S&%1RlZJ&C2"
AUTH_ROOT = HOME / ".minimax" / "auth" / "prod"
CLIENT_CONFIG = (HOME / "Library" / "Application Support" / "MiniMax" /
                 "minimax-agent-cn-config.json")
APP_PLIST = Path("/Applications/MiniMax Code.app/Contents/Info.plist")
CLIENT_APP_NAME = "MiniMax Code"
# 客户端启动时自行刷新 auth.json（约 12 小时有效期）；剩余不足该阈值就
# 在签到前主动启动一次，保证当天 10:05/15:05/20:05 三轮都拿到有效 token。
# 用 /usr/bin/open 绝对路径，避免 launchd 的精简 PATH 找不到命令。
LAUNCH_MARGIN_MIN_DEFAULT = 180
LAUNCH_WAIT_SEC = 20       # 实测启动后约 2 秒落盘，20 秒足够
LAUNCH_POLL_SEC = 2
# 本轮是否真的启动并刷新了客户端；用于把结果带进 report / JSON 便于诊断
LAUNCH_CONTEXT = {"refreshed": False, "note": ""}
# 续期 token 只落在本项目目录，绝不回写客户端 auth.json
TOKEN_CACHE = BASE_DIR / ".minimax_token.json"
CACHE_SOFT_TTL = 7 * 24 * 3600  # renewal 响应不含过期时间，7 天未续上就回落客户端文件

# 官方 daily-signin.ts 的枚举
DAY_UPCOMING, DAY_CLAIMABLE, DAY_CLAIMED, DAY_DISABLED = 1, 2, 3, 4
CLAIM_NEW, CLAIM_ALREADY = 1, 2


def log(msg):
    sys.stderr.write("[MiniMax] %s\n" % msg)


def finish(result, report, **extra):
    if LAUNCH_CONTEXT["refreshed"]:
        # 让「本轮自动启动了客户端」出现在 checkin.log 的日报里，便于事后核对
        report = "%s（%s）" % (report, LAUNCH_CONTEXT["note"])
    obj = {"app": APP, "result": result, "report": report,
           "client_launched": LAUNCH_CONTEXT["refreshed"]}
    obj.update(extra)
    if proto is not None:
        proto.emit(obj)
    else:
        print(json.dumps(obj, ensure_ascii=False))
    return 0 if result in ("CLAIMED", "ALREADY", "DRY_RUN", "SKIP", "RENEWED") else 1


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


def load_token_cache():
    """读本项目续期缓存（0600）；损坏或超过软有效期返回 {}。绝不打印 token。"""
    try:
        data = json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
        token = str(data.get("token") or "").strip()
        updated = int(data.get("updated_at") or 0)
    except Exception:
        return {}
    if not token or not updated or time.time() - updated > CACHE_SOFT_TTL:
        return {}
    return {"token": token,
            "region": str(data.get("region") or "").strip(),
            "user_id": str(data.get("user_id") or "").strip(),
            "updated_at": updated}


def save_token_cache(token, cred, source="renewal"):
    """原子写入 0600 缓存。写失败不影响本轮签到：新 token 仍在内存中可用。"""
    payload = {"token": token, "region": cred["region"],
               "user_id": cred["user_id"], "updated_at": int(time.time()),
               "source": source}
    tmp = TOKEN_CACHE.with_name(TOKEN_CACHE.name + ".tmp")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(str(tmp), str(TOKEN_CACHE))
        os.chmod(str(TOKEN_CACHE), 0o600)
        return True
    except Exception as exc:
        log("续期缓存写入失败：%s" % type(exc).__name__)
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def credential_candidates():
    """按优先级返回去重后的凭据候选：环境变量 > 续期缓存 > 客户端 auth.json。

    不做「expiresAtMs 已过期就丢弃」的硬拦截：那只是客户端的建议刷新时间，
    而且续期接口本身就可能接受它；最终以服务端 401/403 为准。继续保留全部
    候选，才能在「缓存里的旧 token 失效、客户端刚重新登录」时自动回退。
    """
    env_token = os.environ.get("MINIMAX_ACCESS_TOKEN", "").strip().strip('"').strip("'")
    env_user = os.environ.get("MINIMAX_USER_ID", "").strip()
    region = os.environ.get("MINIMAX_REGION", "").strip().lower() or "cn"
    if region not in ORIGINS:
        region = "cn"

    cfg = read_client_config()
    shared = cfg.get("sharedUser") or {}
    user = cfg.get("user") or {}
    default_user = str(shared.get("realUserID") or user.get("realUserID") or "").strip()

    out, seen = [], set()

    def add(token, uid, reg, exp, source):
        token = (token or "").strip()
        if not token or token in seen:
            return
        seen.add(token)
        out.append({"token": token, "user_id": uid or env_user or default_user,
                    "region": reg if reg in ORIGINS else region,
                    "expires_at_ms": exp, "source": source})

    if env_token:
        add(env_token, env_user, region, 0, "env")
    cache = load_token_cache()
    if cache:
        add(cache["token"], cache.get("user_id"), cache.get("region") or region,
            0, "renewal-cache")
    token, exp, found = read_auth_files(region)
    if token:
        add(token, env_user, found or region, exp, "client")

    uid = env_user or default_user or (cache.get("user_id") if cache else "")
    for c in out:
        if not c["user_id"]:
            c["user_id"] = uid
    return out


def load_credentials():
    """兼容旧调用：返回首选凭据；无候选时返回空 token 的占位 dict。"""
    cands = credential_candidates()
    if cands:
        return cands[0]
    return {"token": "", "user_id": "", "region": "cn",
            "expires_at_ms": 0, "source": ""}


def _launch_margin_ms():
    """允许用环境变量调整阈值，便于排查与本地验证。"""
    raw = os.environ.get("MINIMAX_LAUNCH_MARGIN_MIN", "").strip()
    try:
        minutes = int(raw) if raw else LAUNCH_MARGIN_MIN_DEFAULT
    except ValueError:
        minutes = LAUNCH_MARGIN_MIN_DEFAULT
    return max(0, minutes) * 60 * 1000


def _launch_disabled():
    return os.environ.get("MINIMAX_NO_LAUNCH", "").strip().lower() in (
        "1", "true", "yes", "on")


def ensure_client_fresh(region):
    """签到前保证 CN 客户端 token 新鲜：必要时自行启动客户端刷新 auth.json。

    返回 (是否观察到刷新, 说明)。绝不 quit / 重启正在运行的客户端，也绝不
    改写客户端登录态文件；启动失败只记日志，签到照常进行，由服务端判定。
    """
    if _launch_disabled():
        return False, "MINIMAX_NO_LAUNCH=1，跳过自动启动客户端"
    _, before_exp, _ = read_auth_files(region)
    if not before_exp:
        return False, "auth.json 无 expiresAtMs，不擅自启动客户端"
    remaining = before_exp - int(time.time() * 1000)
    if remaining >= _launch_margin_ms():
        return False, "token 剩余约 %d 分钟，无需启动客户端" % (remaining // 60000)

    try:
        proc = subprocess.run(["/usr/bin/open", "-a", CLIENT_APP_NAME],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE, timeout=10)
    except Exception as exc:
        return False, "启动客户端失败：%s: %s" % (type(exc).__name__, exc)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()[:120]
        return False, "启动客户端失败：open 返回 %d%s" % (
            proc.returncode, "（%s）" % err if err else "")

    deadline = time.time() + LAUNCH_WAIT_SEC
    while time.time() < deadline:
        time.sleep(LAUNCH_POLL_SEC)
        _, new_exp, _ = read_auth_files(region)
        if new_exp > before_exp:
            # 缓存里可能存着上一轮 renewal/fallback 的旧 token，优先级高于
            # 客户端文件；刷新成功后删掉它，避免继续拿旧 token 去撞 401。
            # 只删本项目自己的缓存，绝不碰客户端 auth.json。
            try:
                TOKEN_CACHE.unlink()
            except OSError:
                pass
            return True, ("已自行启动 MiniMax Code，auth.json 刷新至 %s"
                          % time.strftime("%Y-%m-%d %H:%M",
                                          time.localtime(new_exp / 1000)))
    # 未见文件变化要分两种：客户端认为 token 仍有效、压根不需要刷新；
    # 或是 token 确实已过期但没能刷新（客户端已运行 / 登录态失效）。
    left_ms = before_exp - int(time.time() * 1000)
    if left_ms > 0:
        return False, ("客户端已启动，token 仍有效（剩余约 %d 分钟），"
                       "auth.json 无需刷新" % (left_ms // 60000))
    return False, ("客户端已启动，但 %d 秒内未刷新已过期的 auth.json"
                   "（客户端可能本就已运行，激活不会触发启动刷新）；沿用现有 token"
                   % LAUNCH_WAIT_SEC)


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
    if path == RENEW_PATH:
        # /v1/api/user/renewal 是旧版/国际区桌面端登录 API，只认 `token:` 头；
        # 沿用 signin 网关的 Authorization: Bearer 会被判
        # 400「请求异常，请检查请求参数」。CN 区即使换成 token 头也恒定
        # 401「登陆失败」：端点与凭据体系不匹配（详见文件头「凭据体系」）。
        del headers["Authorization"]
        headers["token"] = cred["token"]
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


def server_message(body):
    """从网关响应里取服务端文案，只用于诊断，绝不输出凭据。"""
    if not isinstance(body, dict):
        return ""
    for obj in (body.get("statusInfo"), body.get("base_resp")):
        if isinstance(obj, dict):
            msg = str(obj.get("msg") or obj.get("message") or obj.get("status_msg") or "")
            if msg:
                return msg[:80]
    return ""


def try_renew(cred):
    """用旧 token 换新 token。返回 (新token, 失败原因)；每个候选恰好一次，绝不重试。"""
    status, body, err = api_call(cred, RENEW_PATH, "POST", {}, timeout=20)
    msg = server_message(body)
    suffix = "「%s」" % msg if msg else ""
    if status == 0:
        return "", "网络异常：%s" % err
    if status in (401, 403):
        return "", "HTTP %d%s（凭据不适用或已失效；CN 区请启动客户端刷新 auth.json）" % (status, suffix)
    if status != 200:
        return "", "HTTP %d%s" % (status, suffix)
    data = body if isinstance(body, dict) else {}
    inner = data.get("data")
    new_token = ""
    if isinstance(inner, dict):
        new_token = str(inner.get("token") or "").strip()
    if not new_token:
        new_token = str(data.get("token") or "").strip()
    if not new_token:
        base = data.get("base_resp") or {}
        msg = str(base.get("status_msg") or "") if isinstance(base, dict) else ""
        return "", "响应缺少 data.token%s" % ("（%s）" % msg if msg else "")
    return new_token, ""


def renew_one(cred):
    """对单个凭据恰好续期一次，成功即写缓存。返回 (新凭据 or None, 失败原因)。

    一次运行最多发一个 renewal POST：候选回退只走只读的 status 查询，
    确认有效后写缓存让下一轮自动切换，避免无效写请求成倍增加。
    """
    new_token, why = try_renew(cred)
    if new_token:
        save_token_cache(new_token, cred)
        log("续期成功（来源 %s），新 token 已写入本项目 0600 缓存" % cred["source"])
        return dict(cred, token=new_token, expires_at_ms=0, source="renewal"), ""
    return None, why


def renew_enabled(cred, renew_only=False):
    """是否发送 renewal POST。

    CN 区客户端走 OAuth2 refresh_token（account.minimax.cn/oauth2/token），
    与 /v1/api/user/renewal（国际区 JWT + agent.minimax.io）不是一套协议，
    实测对有效 token 也恒定 401。故 CN 默认关闭、国际区默认开启；
    MINIMAX_RENEW=1/0 可强制覆盖，--renew 始终允许显式探测。
    """
    if renew_only:
        return True
    flag = os.environ.get("MINIMAX_RENEW", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    return cred.get("region") == "en"


def run(dry_run=False, renew_only=False, no_renew=False):
    cands = credential_candidates()
    if not cands:
        return finish("NO_AUTH", "未找到 MiniMax Code 登录态；请在客户端登录一次，"
                      "或设置 MINIMAX_ACCESS_TOKEN / MINIMAX_USER_ID")
    if not cands[0]["user_id"]:
        return finish("NO_AUTH", "缺少 realUserID（user_id），签到接口会误报 401；"
                      "请设置 MINIMAX_USER_ID 或登录客户端后重试")

    # 0) CN 区签到前自行保证客户端 token 新鲜：剩余有效期不足阈值就启动
    #    一次 MiniMax Code，等它把 auth.json 刷新后再读凭据。只在所有凭据
    #    都来自客户端文件时才启动（env 注入 / 国际区缓存不需要 GUI）。
    #    --dry-run 与 --renew 保持零副作用，绝不启动客户端。
    if (not dry_run and not renew_only and cands[0]["region"] == "cn"
            and all(c["source"] == "client" for c in cands)):
        refreshed, launch_note = ensure_client_fresh(cands[0]["region"])
        LAUNCH_CONTEXT["refreshed"] = refreshed
        LAUNCH_CONTEXT["note"] = launch_note
        log("自动登录态检查：%s" % launch_note)
        if refreshed:
            cands = credential_candidates()
            if not cands or not cands[0]["user_id"]:
                return finish("NO_AUTH", "客户端刷新后凭据读取失败；"
                              "请在 MiniMax Code 客户端重新登录一次")

    # 1) 续期。--dry-run 严格不发任何写请求：renewal 是 POST，会改变服务端会话。
    #    CN 区默认跳过：该端点属国际区 JWT 协议，发过去必然 401，只是噪声。
    renewed, renew_note = None, ""
    if not dry_run and not no_renew and renew_enabled(cands[0], renew_only):
        renewed, renew_note = renew_one(cands[0])
        if renewed is None:
            log("续期未成功（沿用现有 token，不重复尝试）：%s" % renew_note)
    elif not dry_run and not no_renew and not renew_only:
        log("按 region 跳过 renewal（CN 区不兼容该端点）；"
            "accessToken 由 MiniMax Code 客户端启动时自行刷新")

    if renew_only:
        if renewed:
            return finish("RENEWED", "token 续期成功，已写入 0600 缓存"
                          "（国际区后续签到会滚动续期）", token_source="renewal")
        return finish("NO_AUTH", "token 续期失败：%s；CN 区该端点不适用，"
                      "请打开 MiniMax Code 客户端让它刷新 auth.json，"
                      "或设置 MINIMAX_ACCESS_TOKEN" % (renew_note or "未尝试"))

    active = renewed or cands[0]

    # 2) 状态查询（只读）。首选 token 鉴权失败时用其它候选只读回查一次；
    #    找到有效候选后写入缓存，下一轮就会以它为首选项重新点燃续期链。
    #    续期已成功时不做回退，以免把刚拿到的新 token 覆盖掉。
    status, body, err = api_call(active, STATUS_PATH, "GET", None)
    if status in (401, 403) and renewed is None:
        for c in cands[1:]:
            if c["token"] == active["token"]:
                continue
            s2, b2, e2 = api_call(c, STATUS_PATH, "GET", None)
            if s2 not in (401, 403):
                status, body, err, active = s2, b2, e2, c
                save_token_cache(c["token"], c, source="fallback:" + c["source"])
                log("已切换到有效凭据（来源 %s）并写入缓存" % c["source"])
                break
    if status == 0:
        return finish("ERROR", "网络异常：%s" % err)
    if status in (401, 403):
        hint = ("；脚本已按需自动启动客户端，若仍失败请在 MiniMax Code 里"
                "重新登录一次，或设置 MINIMAX_ACCESS_TOKEN / MINIMAX_USER_ID")
        if renew_note:
            hint += "（本轮续期失败：%s）" % renew_note[:100]
        return finish("NO_AUTH", "鉴权失败 HTTP %d：token 失效或 user_id 不匹配%s"
                      % (status, hint), token_source=active["source"])
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
                      streak_days=streak, points=points_today, renewed=bool(renewed))
    if dry_run:
        return finish("DRY_RUN", "空跑：今天可领（第 %s 天，+%s 积分），未发送领取请求"
                      % (today.get("day_no"), points_today),
                      streak_days=streak, points=points_today)
    if day_state != DAY_CLAIMABLE:
        return finish("SKIP", "今天不可领（面板状态 %s，非可领状态），未发送领取请求"
                      % day_state, streak_days=streak)

    # 只有面板明确「今天可领」才发唯一一次写请求，且绝不重试。
    status, body, err = api_call(active, CLAIM_PATH, "POST", {})
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
                      streak_days=streak, points=points, renewed=bool(renewed))
    if result_code == CLAIM_NEW:
        return finish("CLAIMED", "签到成功 +%s 积分（第 %s 天）"
                      % (points, data.get("day_no")),
                      streak_days=streak, points=points, renewed=bool(renewed))
    return finish("ERROR", "领取返回未知 claim_result=%s（未重复发起）" % result_code)


def main():
    ap = argparse.ArgumentParser(description="MiniMax Code 每日签到")
    ap.add_argument("--renew", action="store_true", help="显式探测续期端点，不签到（CN 区预期 401）")
    ap.add_argument("--dry-run", action="store_true", help="只查状态，不发任何写请求（含续期）")
    ap.add_argument("--no-renew", action="store_true", help="跳过续期（CN 区默认已跳过）")
    ap.add_argument("--json", action="store_true", help="兼容参数：结果本就是结构化输出")
    args = ap.parse_args()
    try:
        return run(dry_run=args.dry_run, renew_only=args.renew, no_renew=args.no_renew)
    except Exception as exc:
        return finish("ERROR", "未预期异常：%s: %s" % (type(exc).__name__, exc))


if __name__ == "__main__":
    sys.exit(main())
