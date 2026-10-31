#!/usr/bin/env bash
#
# mac-ai-auto-checkin 一键安装与配置脚本
# 适用于 macOS 系统 (Intel & Apple Silicon)
#
set -euo pipefail

LABEL="com.user.ai-daily-checkin"
TARGET_DIR="$HOME/.auto-checkin"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "🍎 mac-ai-auto-checkin: macOS AI助手每日自动签到安装"
echo "=========================================================="

# 1. 检查操作系统
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "❌ 错误: 本脚本专门面向 macOS 系统设计，不支持 $(uname -s)。" >&2
    exit 1
fi

# 2. 查找 Python 3 解释器
PYTHON_BIN=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [[ -x "$cand" ]]; then
        PYTHON_BIN="$cand"
        break
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "❌ 错误: 未找到 python3，请确保已安装 Python 3.8+。" >&2
    exit 1
fi
echo "✓ 使用 Python 解释器: $PYTHON_BIN ($($PYTHON_BIN --version))"

# 3. 部署脚本文件到 ~/.auto-checkin
echo "✓ 正在部署脚本到 $TARGET_DIR ..."
mkdir -p "$TARGET_DIR"
cp -f "$REPO_DIR/scripts/"*.py "$TARGET_DIR/"
chmod +x "$TARGET_DIR/run_all.py"

# 创建快速执行命令
cat <<EOF > "$TARGET_DIR/checkin"
#!/bin/bash
exec "$PYTHON_BIN" "$TARGET_DIR/run_all.py" "\$@"
EOF
chmod +x "$TARGET_DIR/checkin"

# 4. 生成 launchd 服务配置
echo "✓ 正在配置 macOS launchd 定时服务..."
mkdir -p "$HOME/Library/LaunchAgents"

sed -e "s|{{PYTHON_BIN}}|$PYTHON_BIN|g" \
    -e "s|{{TARGET_DIR}}|$TARGET_DIR|g" \
    "$REPO_DIR/templates/com.user.ai-daily-checkin.plist.template" > "$PLIST_DST"

plutil -lint "$PLIST_DST" >/dev/null

# 5. 注册 launchd 服务
UID_NUM="$(id -u)"
if launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
    launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
fi
launchctl bootstrap "gui/$UID_NUM" "$PLIST_DST"
echo "✓ launchd 定时服务已注册并激活 (服务名: $LABEL)"

# 6. 客户端及登录态检测自检
echo ""
echo "---------------- 客户端与登录态自检 ----------------"
cd "$TARGET_DIR"
"$PYTHON_BIN" "$TARGET_DIR/run_all.py" || true
echo "----------------------------------------------------"

echo ""
echo "🎉 安装完成！"
echo "📌 常用操作指引："
echo "  • 手动一键签到:   ~/.auto-checkin/checkin"
echo "  • 查看签到日志:   tail -f ~/.auto-checkin/checkin.log"
echo "  • 服务日志目录:   ~/.auto-checkin/launchd.out.log"
echo "  • 彻底卸载服务:   bash $REPO_DIR/uninstall.sh"
echo ""
echo "💡 提示："
echo "  若 Qoder 提示需要钥匙串授权，请在终端手动执行一次："
echo "  python3 ~/.auto-checkin/qoder_signin.py auto"
echo "  在弹出的 macOS 对话框中输入密码并点击「始终允许」即可永久生效。"
echo "=========================================================="
