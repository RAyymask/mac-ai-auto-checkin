#!/usr/bin/env bash
#
# mac-ai-auto-checkin 安装 / 自检脚本（macOS，Intel & Apple Silicon）
#
set -euo pipefail
umask 077

LABEL="com.user.ai-daily-checkin"
TARGET_DIR="$HOME/.auto-checkin"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UID_NUM="$(id -u)"
TEMPLATE="$REPO_DIR/templates/$LABEL.plist.template"

usage() {
  cat <<EOF
用法：bash install.sh [选项]

  （无参数）   部署脚本 + 注册 launchd 定时服务 + 立即试跑一次
  --dry-run    只预览将要做什么，不写文件、不注册、不发送任何网络请求
  --no-run     部署并注册，但不立即试跑
  --check      运行离线自检（doctor），不联网、不读取凭据内容
  -h, --help   显示本帮助

注意：默认安装会立即使用你本机已登录的账号，向 WorkBuddy / Trae / Qoder /
      MiniMax Code / 豆包 的服务器发送签到请求（豆包走未签名接口，详见 README
      的风控说明）。只想准备文件请用 --dry-run 或 --no-run。
EOF
}

MODE="install"
RUN_ONCE=1
case "${1:-}" in
  --dry-run) MODE="dry" ;;
  --no-run)  RUN_ONCE=0 ;;
  --check)   MODE="check" ;;
  -h|--help) usage; exit 0 ;;
  "") ;;
  *) printf '未知参数：%s\n\n' "$1" >&2; usage >&2; exit 2 ;;
esac

if [[ "$(uname -s)" != "Darwin" ]]; then
  printf '错误：仅支持 macOS，当前为 %s\n' "$(uname -s)" >&2
  exit 1
fi

PYTHON_BIN=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [[ -x "$cand" ]]; then PYTHON_BIN="$cand"; break; fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "错误：未找到 python3（需要 3.8+）" >&2
  exit 1
fi
PY_VERSION="$($PYTHON_BIN --version 2>&1)"

if [[ "$MODE" == "check" ]]; then
  echo "使用 Python：$PYTHON_BIN ($PY_VERSION)"
  AUTO_CHECKIN_DIR="$TARGET_DIR" "$PYTHON_BIN" "$REPO_DIR/scripts/doctor.py" "${@:2}"
  exit $?
fi

if [[ "$MODE" == "dry" ]]; then
  echo "=========== dry-run（不写文件、不注册、不发请求）==========="
  echo "Python：$PYTHON_BIN ($PY_VERSION)"
  echo "将部署：$REPO_DIR/scripts/*.py -> $TARGET_DIR （目录 700，文件 600）"
  echo "将生成：$PLIST_DST"
  echo "将注册：launchctl bootstrap gui/$UID_NUM $PLIST_DST"
  echo "将试跑：$PYTHON_BIN $TARGET_DIR/run_all.py （会向五个平台发送签到请求）"
  echo "-------- 生成的 plist 预览 --------"
  sed -e "s|{{PYTHON_BIN}}|$PYTHON_BIN|g" -e "s|{{TARGET_DIR}}|$TARGET_DIR|g" "$TEMPLATE"
  echo "-------------------------------------------------------------"
  echo "未创建文件、未注册服务、未发送任何网络请求。"
  exit 0
fi

echo "=========================================================="
echo "🍎 mac-ai-auto-checkin 安装"
echo "=========================================================="
echo "✓ Python：$PYTHON_BIN ($PY_VERSION)"

FILES_OK=0
SERVICE_OK=0
RUN_OK=0

echo "✓ [1/3] 部署脚本到 $TARGET_DIR"
mkdir -p "$TARGET_DIR"
cp -f "$REPO_DIR/scripts/"*.py "$TARGET_DIR/"
chmod 700 "$TARGET_DIR"
chmod 600 "$TARGET_DIR/"*.py
chmod 700 "$TARGET_DIR/run_all.py" "$TARGET_DIR/doctor.py"
cat > "$TARGET_DIR/checkin" <<EOF
#!/bin/bash
case "\${1:-}" in
  doctor|status|--check)
    shift
    exec "$PYTHON_BIN" "$TARGET_DIR/doctor.py" "\$@"
    ;;
  *)
    exec "$PYTHON_BIN" "$TARGET_DIR/run_all.py" "\$@"
    ;;
esac
EOF
chmod 700 "$TARGET_DIR/checkin"
for f in "$TARGET_DIR"/*.json "$TARGET_DIR"/.trae_token_cache.json; do
  if [[ -f "$f" ]]; then chmod 600 "$f"; fi
done
FILES_OK=1

echo "✓ [2/3] 生成并注册 launchd 服务"
mkdir -p "$HOME/Library/LaunchAgents"

# 先写临时文件并校验，避免用一份坏 plist 覆盖掉线上配置
PLIST_TMP="$TARGET_DIR/.launchagent.plist.new"
sed -e "s|{{PYTHON_BIN}}|$PYTHON_BIN|g" \
    -e "s|{{TARGET_DIR}}|$TARGET_DIR|g" \
    "$TEMPLATE" > "$PLIST_TMP"
plutil -lint "$PLIST_TMP" >/dev/null

# 只比较影响调度的字段；RunAtLoad 仅在加载瞬间生效，不算差异
config_matches() {
  [[ -f "$PLIST_DST" ]] || return 1
  "$PYTHON_BIN" - "$PLIST_DST" "$PLIST_TMP" <<'PY'
import plistlib, sys
try:
    old = plistlib.load(open(sys.argv[1], 'rb'))
    new = plistlib.load(open(sys.argv[2], 'rb'))
except Exception:
    sys.exit(1)
keys = ('Label', 'ProgramArguments', 'StartCalendarInterval',
        'WorkingDirectory', 'StandardOutPath', 'StandardErrorPath')
sys.exit(0 if all(old.get(k) == new.get(k) for k in keys) else 1)
PY
}

BOOTSTRAP_ERR="$TARGET_DIR/bootstrap.err"
SERVICE_LOST=0
SERVICE_LOADED=0
CONFIG_SAME=0
launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 && SERVICE_LOADED=1
# 比对必须在替换 PLIST_DST 之前完成，否则读到的是刚写好的新文件
if [[ "$SERVICE_LOADED" -eq 1 ]] && config_matches; then CONFIG_SAME=1; fi

mv -f "$PLIST_TMP" "$PLIST_DST"
chmod 644 "$PLIST_DST"

if [[ "$SERVICE_LOADED" -eq 1 && "$CONFIG_SAME" -eq 1 ]]; then
  # 服务已注册且调度一致：不要为了一份等价的 plist 注销掉健康的后台服务。
  # 在受限会话里可能 bootout 成功、bootstrap 却被拒，那样服务就彻底丢了。
  SERVICE_OK=1
  echo "  · 服务已注册且排程一致，保留现有注册；磁盘配置已更新，重新登录后完全同步"
  rm -f "$BOOTSTRAP_ERR"
else
  if [[ "$SERVICE_LOADED" -eq 1 ]]; then
    echo "  · 调度配置有变化，重新注册服务…"
    launchctl bootout "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 || true
    SERVICE_LOST=1
  fi
  if launchctl bootstrap "gui/$UID_NUM" "$PLIST_DST" 2>"$BOOTSTRAP_ERR"; then
    SERVICE_OK=1
    SERVICE_LOST=0
    rm -f "$BOOTSTRAP_ERR"
  else
    printf '✗ launchctl bootstrap 失败：\n' >&2
    if [[ -s "$BOOTSTRAP_ERR" ]]; then sed 's/^/    /' "$BOOTSTRAP_ERR" >&2; fi
  fi
fi

if [[ "$RUN_ONCE" -eq 1 ]]; then
  echo "✓ [3/3] 立即试跑一次（会发送网络请求）"
  echo "---------------- 试跑输出 ----------------"
  set +e
  (cd "$TARGET_DIR" && "$PYTHON_BIN" "$TARGET_DIR/run_all.py")
  RUN_RC=$?
  set -e
  echo "------------------------------------------"
  if [[ "$RUN_RC" -eq 0 ]]; then RUN_OK=1; fi
else
  echo "○ [3/3] 已跳过试跑（--no-run）"
fi

mark() { if [[ "$1" -eq 1 ]]; then printf 'OK'; else printf 'FAILED'; fi; }
echo ""
echo "=============== 安装结果（三态）==============="
printf '  [%-6s] 1/3 文件部署    %s\n' "$(mark "$FILES_OK")" "$TARGET_DIR"
printf '  [%-6s] 2/3 服务注册    gui/%s/%s\n' "$(mark "$SERVICE_OK")" "$UID_NUM" "$LABEL"
if [[ "$RUN_ONCE" -eq 1 ]]; then
  printf '  [%-6s] 3/3 试跑验证\n' "$(mark "$RUN_OK")"
else
  printf '  [%-6s] 3/3 试跑验证（--no-run 跳过）\n' "SKIP"
fi
echo "=============================================="

if [[ "$SERVICE_OK" -ne 1 ]]; then
  cat <<EOF

⚠️  文件已部署，但定时服务未注册 —— 本次会话不会自动签到。
    这不是「安装完成」，请按顺序排查：

  1. 当前会话 launchctl managername = $(launchctl managername 2>&1)
     若是 Background 或 SSH 会话，请在图形界面的「终端」里重跑：
       launchctl bootstrap gui/$UID_NUM "$PLIST_DST"
  2. macOS 13+：检查「系统设置 → 通用 → 登录项与扩展」里是否有待批准的后台项。
  3. 文件已就位：重新登录 macOS 后，launchd 通常会自动加载该目录下的 plist。
  4. 离线自检：bash install.sh --check
  5. 完整错误输出：$BOOTSTRAP_ERR
EOF
  if [[ "$SERVICE_LOST" -eq 1 ]]; then
    cat <<EOF

🚨 注意：本次为替换配置，原有服务已被注销且新服务注册失败，当前没有任何定时服务。
   请在图形界面的「终端」里执行下面这条命令恢复：
     launchctl bootstrap gui/$UID_NUM "$PLIST_DST"
EOF
  fi
fi

if [[ "$SERVICE_OK" -ne 1 ]]; then exit 1; fi
if [[ "$RUN_ONCE" -eq 1 && "$RUN_OK" -ne 1 ]]; then exit 2; fi

echo ""
echo "🎉 安装完成。"
echo "  手动签到：~/.auto-checkin/checkin"
echo "  离线自检：~/.auto-checkin/checkin doctor"
echo "  查看日志：tail -f ~/.auto-checkin/checkin.log"
echo "  Qoder 钥匙串首次授权：python3 ~/.auto-checkin/qoder_signin.py auto（弹窗选「始终允许」）"
echo "  卸载：bash $REPO_DIR/uninstall.sh"
exit 0
