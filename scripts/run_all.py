#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 助手每日一键自动签到脚本 (WorkBuddy, Trae, Qoder)
支持自动读取本地桌面端登录凭据，静默调用官方 API 完成签到与积分领取。
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "checkin.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def send_notification(title, subtitle, message):
    """发送 macOS 系统原生通知"""
    try:
        script = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception:
        pass

def checkin_workbuddy():
    """WorkBuddy 每日签到与成长中心任务"""
    log("▶ [WorkBuddy] 开始执行签到...")
    script = BASE_DIR / "signin.py"
    if not script.exists():
        return {"status": "SKIP", "msg": "未找到 signin.py"}
    
    try:
        res = subprocess.run(
            [sys.executable, str(script), "auto"],
            capture_output=True,
            text=True,
            timeout=30
        )
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    res_type = data.get("result")
                    streak = data.get("streak_days", 0)
                    total = data.get("total_credits", 0)
                    if res_type in ("CLAIMED", "ALREADY"):
                        status_str = "今日已签" if res_type == "ALREADY" else "签到成功"
                        msg = f"{status_str} (+{data.get('today_credit', 100)}积分)，连签 {streak} 天，累计 {total}"
                        log(f"  ✓ [WorkBuddy] {msg}")
                        return {"status": "OK", "msg": msg}
                    else:
                        report = data.get("report", "未知状态")
                        log(f"  ℹ [WorkBuddy] {report}")
                        return {"status": "WARN", "msg": report}
                except json.JSONDecodeError:
                    pass
        return {"status": "FAIL", "msg": res.stderr.strip() or "执行无有效返回"}
    except Exception as e:
        log(f"  ✗ [WorkBuddy] 异常: {e}")
        return {"status": "FAIL", "msg": str(e)}

def checkin_trae():
    """Trae 每日签到与额度查询"""
    log("▶ [Trae] 开始执行签到...")
    token_helper = BASE_DIR / "trae_get_token.py"
    checkin_script = BASE_DIR / "trae_checkin.py"
    if not (token_helper.exists() and checkin_script.exists()):
        return {"status": "SKIP", "msg": "未找到 Trae 脚本"}
    
    try:
        import trae_get_token
        accounts = []
        for p in trae_get_token.candidate_paths():
            acc = trae_get_token.extract(p)
            if acc:
                acc['realDeviceId'] = trae_get_token.device_id_in(p)
                acc['name'] = acc.get('nickname') or f"UID_{acc.get('uid')}"
                accounts.append(acc)
                break
        
        if not accounts:
            log("  ✗ [Trae] 未在本地发现 Trae 客户端登录凭据")
            return {"status": "FAIL", "msg": "未检测到本地登录态"}
        
        env = dict(os.environ, TRAE_ACCOUNTS=json.dumps(accounts), TRAE_JITTER="0")
        res = subprocess.run(
            [sys.executable, str(checkin_script)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        out = res.stdout
        if "签到成功" in out or "今日已签到" in out or "已签到" in out:
            # 提取余额
            balance = ""
            for line in out.splitlines():
                if "当前余额" in line:
                    balance = line.split("当前余额")[-1].strip()
                    break
            status_text = "签到成功" if "签到成功（已回查确认）" in out else "今日已完成"
            bal_text = f"，当前额度 {balance}" if balance else ""
            msg = f"{status_text} (+100积分){bal_text}"
            log(f"  ✓ [Trae] {msg}")
            return {"status": "OK", "msg": msg}
        else:
            err_line = res.stderr.strip() or "签到失败"
            log(f"  ✗ [Trae] {err_line}")
            return {"status": "FAIL", "msg": err_line}
    except Exception as e:
        log(f"  ✗ [Trae] 异常: {e}")
        return {"status": "FAIL", "msg": str(e)}

def checkin_qoder():
    """Qoder CN 每日 100 Credits 领取"""
    log("▶ [Qoder] 开始执行签到...")
    script = BASE_DIR / "qoder_signin.py"
    if not script.exists():
        return {"status": "SKIP", "msg": "未找到 qoder_signin.py"}
    
    try:
        res = subprocess.run(
            [sys.executable, str(script), "auto"],
            capture_output=True,
            text=True,
            timeout=25
        )
        
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    result_type = data.get("result")
                    if result_type in ("CLAIMED", "ALREADY"):
                        status_str = "已领今日 100 Credits" if result_type == "ALREADY" else "成功领取 100 Credits"
                        log(f"  ✓ [Qoder] {status_str}")
                        return {"status": "OK", "msg": status_str}
                    elif result_type == "NO_AUTH":
                        report = data.get("report", "需要登录态")
                        log(f"  ⚠️ [Qoder] {report}")
                        return {"status": "AUTH_NEEDED", "msg": "需钥匙串授权（终端运行一次即可激活）"}
                    else:
                        report = data.get("report", "未知状态")
                        log(f"  ℹ [Qoder] {report}")
                        return {"status": "WARN", "msg": report}
                except json.JSONDecodeError:
                    pass
        
        # 错误分析
        if "读取钥匙串失败" in res.stdout or "读取钥匙串失败" in res.stderr:
            log("  ⚠️ [Qoder] 钥匙串访问需初次授权")
            return {"status": "AUTH_NEEDED", "msg": "需钥匙串授权（终端运行一次即可激活）"}
        
        return {"status": "FAIL", "msg": "执行未产生有效输出"}
    except Exception as e:
        log(f"  ✗ [Qoder] 异常: {e}")
        return {"status": "FAIL", "msg": str(e)}

def main():
    log("=" * 55)
    log("🚀 启动 AI 办公助手每日自动签到")
    
    results = {}
    results["WorkBuddy"] = checkin_workbuddy()
    results["Trae"] = checkin_trae()
    results["Qoder"] = checkin_qoder()
    
    log("-" * 55)
    summary_lines = []
    for app, info in results.items():
        icon = "✅" if info["status"] == "OK" else ("⚠️" if info["status"] in ("WARN", "AUTH_NEEDED") else "❌")
        summary_lines.append(f"{icon} {app}: {info['msg']}")
        log(f"{icon} {app}: {info['msg']}")
    log("=" * 55 + "\n")
    
    # 触发 macOS 桌面通知
    notify_body = "\\n".join(summary_lines)
    send_notification("每日签到助手", "AI 助手积分领取完毕", notify_body)

if __name__ == "__main__":
    main()
