#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mac-ai-auto-checkin 离线自检。

不发送任何网络请求，不读取也不打印凭据内容，只报告「文件 / 服务 / 日志」三态。

用法：
    python3 ~/.auto-checkin/doctor.py
    python3 ~/.auto-checkin/doctor.py --json
"""

import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "com.user.ai-daily-checkin"
CATCHUP_LABEL = "com.user.ai-daily-checkin.catchup"
BASE = Path(os.environ.get("AUTO_CHECKIN_DIR") or Path(__file__).resolve().parent).resolve()
HOME = Path.home()
PLIST = HOME / "Library" / "LaunchAgents" / (LABEL + ".plist")
CATCHUP_PLIST = HOME / "Library" / "LaunchAgents" / (CATCHUP_LABEL + ".plist")
LOG = BASE / "checkin.log"

CLIENTS = (
    ("WorkBuddy", ("WorkBuddy.app",)),
    ("Trae CN", ("Trae CN.app",)),
    ("Qoder CN", ("Qoder CN.app", "Qoder.app")),
    ("MiniMax Code", ("MiniMax Code.app",)),
    ("豆包", ("Doubao.app",)),
)
SCRIPTS = ("checkin_protocol.py", "run_all.py", "signin.py", "trae_get_token.py",
           "trae_checkin.py", "qoder_signin.py", "minimax_checkin.py",
           "doubao_checkin.py", "catchup.py", "doctor.py")


def rec(name, ok, detail, fix=""):
    return {"name": name, "ok": bool(ok), "detail": detail, "fix": fix}


def service_loaded(label=LABEL):
    try:
        r = subprocess.run(["launchctl", "print", "gui/%d/%s" % (os.getuid(), label)],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def collect():
    items = []
    py = sys.version_info
    items.append(rec("Python", py >= (3, 8),
                     "%d.%d.%d  %s" % (py.major, py.minor, py.micro, sys.executable),
                     "" if py >= (3, 8) else "需要 Python 3.8+"))

    for label, names in CLIENTS:
        found = [n for n in names if (Path("/Applications") / n).is_dir()]
        items.append(rec("客户端 " + label, bool(found),
                         "已安装：" + "、".join(found) if found else "未在 /Applications 找到",
                         "" if found else "安装并至少登录一次 " + label))

    missing = [s for s in SCRIPTS if not (BASE / s).is_file()]
    items.append(rec("脚本完整性", not missing,
                     "全部 %d 个脚本就位" % len(SCRIPTS) if not missing
                     else "缺失：" + "、".join(missing),
                     "重新运行 install.sh" if missing else ""))

    bad = []
    for s in SCRIPTS:
        p = BASE / s
        if not p.is_file():
            continue
        try:
            compile(p.read_text(encoding="utf-8"), s, "exec")
        except Exception as exc:
            bad.append("%s (%s)" % (s, type(exc).__name__))
    items.append(rec("语法检查", not bad,
                     "全部通过" if not bad else "失败：" + "、".join(bad),
                     "重新运行 install.sh" if bad else ""))

    try:
        mode = BASE.stat().st_mode & 0o777
        ok = (mode & 0o077) == 0
        items.append(rec("目录权限", ok, "%s 为 %o" % (BASE, mode),
                         "chmod 700 %s" % BASE if not ok else ""))
    except Exception as exc:
        items.append(rec("目录权限", False, "读取失败：%s" % exc))

    # 只检查权限，不读取内容：Trae 的 refreshToken 与 MiniMax 续期得到的
    # accessToken 都属于明文凭据，必须是 0600。
    for cache_name in (".trae_token_cache.json", ".minimax_token.json"):
        cache = BASE / cache_name
        if not cache.exists():
            continue
        mode = cache.stat().st_mode & 0o777
        ok = (mode & 0o077) == 0
        items.append(rec("凭据缓存权限 " + cache_name, ok,
                         "%s 为 %o（内容不读取）" % (cache_name, mode),
                         "chmod 600 %s" % cache if not ok else ""))

    # 新增两个平台的凭据链路静态检查：只看文件是否存在 / 工具是否可用，
    # 不读取任何 token、cookie 内容，也不联网、不触发钥匙串授权弹窗。
    openssl_path = shutil.which("openssl") or "/usr/bin/openssl"
    has_openssl = Path(openssl_path).is_file()
    items.append(rec("openssl（豆包解密）", has_openssl,
                     openssl_path if has_openssl else "未找到 openssl",
                     "" if has_openssl else "安装 Xcode Command Line Tools"))

    doubao_db = HOME / "Library" / "Application Support" / "Doubao" / "Default" / "Cookies"
    items.append(rec("豆包登录态文件", doubao_db.is_file(),
                     str(doubao_db) if doubao_db.is_file() else "未找到客户端 Cookie 库",
                     "" if doubao_db.is_file() else "安装并登录一次豆包电脑版"))

    mm_root = HOME / ".minimax" / "auth" / "prod"
    mm_files = list(mm_root.glob("*/mcode-public/auth.json")) if mm_root.is_dir() else []
    items.append(rec("MiniMax 登录态文件", bool(mm_files),
                     "已找到 %d 份认证文件（内容不读取）" % len(mm_files) if mm_files
                     else "未找到 ~/.minimax/auth/prod/*/mcode-public/auth.json",
                     "" if mm_files else "在 MiniMax Code 客户端登录一次"))

    if not PLIST.exists():
        items.append(rec("LaunchAgent 配置", False, "%s 不存在" % PLIST,
                         "运行 install.sh"))
    else:
        try:
            with open(PLIST, "rb") as f:
                data = plistlib.load(f)
            slots = data.get("StartCalendarInterval") or []
            times = "、".join("%02d:%02d" % (d.get("Hour", 0), d.get("Minute", 0))
                             for d in slots) or "无"
            run_at_load = bool(data.get("RunAtLoad", False))
            ok = (data.get("Label") == LABEL) and not run_at_load
            items.append(rec("LaunchAgent 配置", ok,
                             "Label=%s；RunAtLoad=%s；排程 %s"
                             % (data.get("Label"), run_at_load, times),
                             "" if ok else
                             "重新运行 install.sh 生成新版 plist（去掉 RunAtLoad，避免重复签到）"))
        except Exception as exc:
            items.append(rec("LaunchAgent 配置", False, "plist 解析失败：%s" % exc,
                             "重新运行 install.sh"))

    loaded = service_loaded()
    items.append(rec("定时服务", loaded,
                     "已注册并激活" if loaded else "未注册（本次会话不会自动运行）",
                     "" if loaded else
                     "手动注册：launchctl bootstrap gui/$(id -u) %s\n"
                     "或重新登录 macOS：launchd 会自动加载 ~/Library/LaunchAgents 下的 plist\n"
                     "若仍失败，检查「系统设置 → 通用 → 登录项与扩展」是否待批准" % PLIST))

    # 开机补签是第二个 LaunchAgent：只在 RunAtLoad 时跑一次，且必须继承主服务
    # 的 EnvironmentVariables（例如 DOUBAO_DISABLE=1），否则会绕过本机停用配置。
    if not CATCHUP_PLIST.exists():
        items.append(rec("开机补签服务", False, "%s 不存在" % CATCHUP_PLIST,
                         "重新运行 install.sh"))
    else:
        try:
            with open(CATCHUP_PLIST, "rb") as f:
                cdata = plistlib.load(f)
            run_at_load = bool(cdata.get("RunAtLoad", False))
            has_calendar = bool(cdata.get("StartCalendarInterval"))
            env_obj = cdata.get("EnvironmentVariables") or {}
            env_names = sorted(env_obj.keys()) if isinstance(env_obj, dict) else []
            cfg_ok = (cdata.get("Label") == CATCHUP_LABEL and run_at_load
                      and not has_calendar and (BASE / "catchup.py").is_file())
            c_loaded = service_loaded(CATCHUP_LABEL)
            detail = ("RunAtLoad=%s；日历排程=%s；继承环境变量=%s；服务=%s"
                      % (run_at_load, "有" if has_calendar else "无",
                         "、".join(env_names) or "无",
                         "已注册" if c_loaded else "未注册"))
            items.append(rec("开机补签服务", cfg_ok and c_loaded, detail,
                             "" if (cfg_ok and c_loaded) else
                             ("重新运行 install.sh" if not cfg_ok else
                              "手动注册：launchctl bootstrap gui/$(id -u) %s\n"
                              "或重新登录 macOS 让 launchd 自动加载" % CATCHUP_PLIST)))
        except Exception as exc:
            items.append(rec("开机补签服务", False, "plist 解析失败：%s" % exc,
                             "重新运行 install.sh"))

    if LOG.exists():
        lines = [x for x in LOG.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
        items.append(rec("签到日志", True,
                         "%.1f KB；最后一条：%s"
                         % (LOG.stat().st_size / 1024.0,
                            (lines[-1] if lines else "(空)")[:120])))
    else:
        items.append(rec("签到日志", False, "尚无签到记录",
                         "运行 ~/.auto-checkin/checkin"))

    for name in ("launchd.out.log", "launchd.err.log"):
        p = BASE / name
        if p.exists() and p.stat().st_size > 1024 * 1024:
            items.append(rec("launchd 日志体积", False,
                             "%s 已 %.1f MB" % (name, p.stat().st_size / 1024.0 / 1024),
                             "可清空：> %s" % p))
    return items


def main():
    items = collect()
    failed = [i for i in items if not i["ok"]]
    if "--json" in sys.argv[1:]:
        print(json.dumps({"ok": not failed, "items": items},
                         ensure_ascii=False, indent=2))
        return 0 if not failed else 1

    print("mac-ai-auto-checkin 自检（不联网、不读取凭据内容）")
    print("-" * 72)
    for i in items:
        print("%s %-16s %s" % ("[OK]" if i["ok"] else "[!!]", i["name"], i["detail"]))
        if i["fix"] and not i["ok"]:
            for line in i["fix"].splitlines():
                print("       -> %s" % line)
    print("-" * 72)
    if failed:
        print("结论：%d 项需要处理" % len(failed))
        if not next((i["ok"] for i in items if i["name"] == "定时服务"), True):
            print("      文件仍已就位；服务未注册时，重新登录 macOS 通常会自动加载 plist。")
    else:
        print("结论：全部检查通过")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
