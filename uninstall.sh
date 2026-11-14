#!/usr/bin/env bash
#
# mac-ai-auto-checkin 卸载脚本（非交互）
#
set -euo pipefail

LABEL="com.user.ai-daily-checkin"
CATCHUP_LABEL="com.user.ai-daily-checkin.catchup"
TARGET_DIR="$HOME/.auto-checkin"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"
CATCHUP_DST="$HOME/Library/LaunchAgents/$CATCHUP_LABEL.plist"
UID_NUM="$(id -u)"

usage() {
  cat <<EOF
用法：bash uninstall.sh [选项]

  （无参数）   注销定时服务并删除 plist，保留 ~/.auto-checkin 脚本与日志
  --purge      连同 ~/.auto-checkin 目录一并删除（不可恢复，含历史日志与缓存）
  -h, --help   显示本帮助

卸载后仍有一项系统级授权需要你手动撤销，见脚本结束时的提示。
EOF
}

PURGE=0
case "${1:-}" in
  --purge)   PURGE=1 ;;
  -h|--help) usage; exit 0 ;;
  "") ;;
  *) printf '未知参数：%s\n\n' "$1" >&2; usage >&2; exit 2 ;;
esac

echo "=========================================================="
echo "🗑️  卸载 mac-ai-auto-checkin"
echo "=========================================================="

LABELS=("$LABEL" "$CATCHUP_LABEL")
PLISTS=("$PLIST_DST" "$CATCHUP_DST")
for i in 0 1; do
  agent="${LABELS[$i]}"
  plist="${PLISTS[$i]}"
  if launchctl print "gui/$UID_NUM/$agent" >/dev/null 2>&1; then
    echo "✓ 正在注销 $agent ..."
    launchctl bootout "gui/$UID_NUM/$agent" >/dev/null 2>&1 || true
  else
    echo "ℹ $agent 当前未注册，跳过注销"
  fi
  if [[ -f "$plist" ]]; then
    rm -f "$plist"
    echo "✓ 已移除 $plist"
  else
    echo "ℹ $plist 不存在，跳过"
  fi
done

if [[ "$PURGE" -eq 1 ]]; then
  if [[ -d "$TARGET_DIR" ]]; then
    rm -rf "$TARGET_DIR"
    echo "✓ 已删除 ${TARGET_DIR}（脚本、日志与凭据缓存）"
  fi
else
  echo "ℹ 保留 ${TARGET_DIR}（脚本与历史日志）"
  echo "  如需彻底清理，改用：bash uninstall.sh --purge"
fi

cat <<'EOF'

⚠️  还需要你手动完成两件事（脚本无权、也不应替你修改系统授权）：

  1. 撤销 Qoder / 豆包的钥匙串「始终允许」授权
     安装时若点过「始终允许」，macOS 会为 python3 / security 永久放行该项，卸载不会自动撤销。
     打开「钥匙串访问」→ 登录 → 密码类，分别找到：
       · Qoder CN App Safe Storage        （Qoder）
       · Doubao Browser Safe Storage     （豆包，回退项 Doubao Safe Storage）
     → 双击 → 访问控制 → 删除 python3 / security 对应的条目，或改回「每次询问」。
     使用 --purge 时，~/.auto-checkin/.minimax_token.json 里的续期 token 会随目录一并删除。

  2. 检查后台项残留
     「系统设置 → 通用 → 登录项与扩展」里如有本项目的后台项，请手动移除。
EOF

echo ""
echo "🎉 卸载完成。"
echo "=========================================================="
