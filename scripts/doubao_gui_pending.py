#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包 GUI 兜底的状态机：登记 / 查询 / 销账。

为什么需要
  launchd 启动的 python3 **没有辅助功能权限**（本机实测
  ``AXIsProcessTrusted() == False``），无法在无人值守时投递真实鼠标事件；
  终端 / WorkBuddy 会话里的同一份 python3 却是 ``True``。因此裸 HTTP 脚本
  失败后不能由脚本自己点客户端，只能登记待办，交给有 GUI 通道的会话接管。

  本模块不联网、不发签到请求，只维护两个 0600 状态文件，保证
  「脚本一天一次 + GUI 兜底一天一次」且当天不再重试任何通道。

  WorkBuddy 侧每天有三个检查点（10:15 / 15:15 / 20:15），任何一个在线
  都能接手待办；但**真实鼠标点击一天最多一次**。点击前必须先
  ``--attempted`` 落盘标记，后续检查点看到 ``gui_attempted=true`` 时
  只允许做只读复验与销账，绝不再次点击。标记与待办同文件、同日过期，
  跨天自动重置。

状态文件（都在 ~/.auto-checkin/）
  .doubao_gui_pending   JSON {date, reason, ts, gui_attempted, attempted_ts}，
                        存在且 date 为今天时表示待办
  .doubao_done          纯文本 YYYY-MM-DD，当天已处理守卫（run_all.py 也写）

用法
  python3 doubao_gui_pending.py --status      # 只读查询；顺手清理过期待办
  python3 doubao_gui_pending.py --attempted   # 标记本日已投递一次 GUI 点击
  python3 doubao_gui_pending.py --done        # 销账：写当天守卫并删除待办
  python3 doubao_gui_pending.py --mark "原因"  # 登记（一般供测试 / 手工用）

约束
  * --status 一律退出 0，``pending`` 字段才表示是否有当日待办；
    同时返回 ``gui_attempted`` 布尔值供自动化判断是否还允许点击。
  * --attempted 只在存在当日待办时生效，不会凭空创建待办。
  * 过期待办（非今天）不视为有效，并在 --status 时删除，避免跨天误签。
  * 不使用 DOUBAO_FORCE，不调用 doubao_checkin.py 的写模式。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PENDING = BASE_DIR / ".doubao_gui_pending"
DONE = BASE_DIR / ".doubao_done"
DATE_FMT = "%Y-%m-%d"
TS_FMT = "%Y-%m-%d %H:%M:%S"


def today():
    return datetime.now().strftime(DATE_FMT)


def _write_private(path, text):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def read_pending():
    """返回当天的待办 dict；文件损坏、缺失或过期都返回 None。"""
    try:
        obj = json.loads(PENDING.read_text(encoding="utf-8"))
        if isinstance(obj, dict) and obj.get("date") == today():
            return obj
    except Exception:
        pass
    return None


def _drop_stale():
    """清掉非今天的残留待办，避免跨天误判（不报缺省文件）。"""
    try:
        obj = json.loads(PENDING.read_text(encoding="utf-8"))
        if isinstance(obj, dict) and obj.get("date") != today():
            PENDING.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def mark(reason):
    _write_private(PENDING, json.dumps({
        "date": today(),
        "reason": str(reason)[:500],
        "ts": datetime.now().strftime(TS_FMT),
        "gui_attempted": False,
    }, ensure_ascii=False))


def attempted():
    """在投递真实鼠标点击**之前**落盘标记，保证同一天最多点一次。

    只在存在当日待办时写入；返回是否标记成功。这样即使点击后进程中断，
    下一个检查点也不会重复点击，只会做只读复验。
    """
    p = read_pending()
    if not p:
        return False
    p["gui_attempted"] = True
    p["attempted_ts"] = datetime.now().strftime(TS_FMT)
    _write_private(PENDING, json.dumps(p, ensure_ascii=False))
    return True


def done():
    """GUI 兜底完成后销账：写当天守卫 + 删除待办。"""
    _write_private(DONE, today())
    try:
        PENDING.unlink()
    except Exception:
        pass


def main():
    args = sys.argv[1:]
    if "--status" in args:
        _drop_stale()
        p = read_pending()
        out = {"pending": p is not None}
        if p:
            out.update(p)
        out["gui_attempted"] = bool(p.get("gui_attempted")) if p else False
        print(json.dumps(out, ensure_ascii=False))
        return 0
    if "--attempted" in args:
        ok = attempted()
        print(json.dumps({"attempted": ok, "date": today()}, ensure_ascii=False))
        return 0
    if "--done" in args:
        done()
        print(json.dumps({"done": True, "date": today()}, ensure_ascii=False))
        return 0
    if "--mark" in args:
        i = args.index("--mark")
        reason = args[i + 1] if i + 1 < len(args) else "未说明"
        mark(reason)
        print(json.dumps({"marked": True, "date": today()}, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
