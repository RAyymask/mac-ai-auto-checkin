#!/usr/bin/env bash
#
# mac-ai-auto-checkin 一键卸载脚本
#
set -euo pipefail

LABEL="com.user.ai-daily-checkin"
TARGET_DIR="$HOME/.auto-checkin"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "=========================================================="
echo "🗑️ 卸载 mac-ai-auto-checkin"
echo "=========================================================="

UID_NUM="$(id -u)"

# 1. 注销 launchd
if launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
    echo "✓ 正在注销 launchd 定时服务..."
    launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
fi

# 2. 删除 plist
if [[ -f "$PLIST_DST" ]]; then
    rm -f "$PLIST_DST"
    echo "✓ 已移除 LaunchAgent 配置文件: $PLIST_DST"
fi

# 3. 询问是否清理脚本目录
read -r -p "是否删除 ~/.auto-checkin 目录及日志文件？(y/N): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    rm -rf "$TARGET_DIR"
    echo "✓ 已清理目录: $TARGET_DIR"
else
    echo "ℹ 已保留 $TARGET_DIR 目录及历史日志。"
fi

echo "🎉 卸载完成！"
echo "=========================================================="
