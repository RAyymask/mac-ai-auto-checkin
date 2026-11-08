# 🍎 mac-ai-auto-checkin

<p align="center">
  <strong>专为 macOS 打造的 AI 办公与编程助手每日自动一键签到 & 积分领取套件</strong><br>
  涵盖 <strong>WorkBuddy</strong> (腾讯) · <strong>Trae CN</strong> (字节跳动) · <strong>Qoder CN</strong><br>
  <strong>MiniMax Code</strong> (MiniMax) · <strong>豆包</strong> (字节跳动)
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-macOS%2011.0%2B-black?logo=apple&style=flat-square" alt="macOS">
  <img src="https://img.shields.io/badge/Arch-Apple%20Silicon%20%7C%20Intel-blue?style=flat-square" alt="Architecture">
  <img src="https://img.shields.io/badge/Python-3.8%2B%20(Zero--Dep)-3776AB?logo=python&logoColor=white&style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/Scheduler-macOS%20launchd-007AFF?style=flat-square" alt="launchd">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

---

## ⚠️ 使用前必读

* **本项目调用的是各客户端的未公开接口**，并非官方签到入口。自动化领取积分、以及 Trae 的设备指纹对齐逻辑，可能违反对应平台的服务条款，存在账号被限制的风险。请自行评估。
* **默认安装 (`bash install.sh`) 会立即使用你本机已登录的账号，向五个平台发送签到请求**。只想准备文件、不发起任何请求，请用 `--dry-run`（纯预览）或 `--no-run`（部署+注册但不试跑）。
* 安装过程会**读取本机客户端的登录态**，Qoder 与豆包部分还会读取 macOS 钥匙串。首次可能弹出系统授权对话框，请在「终端」里手动跑一次并选「始终允许」。
* **豆包走的是未签名裸 HTTP 接口**：上游实测连续请求可能让整个会话被降权，连客户端手工签到都会失效。项目已加「每天最多一次 + 写请求绝不重试」的约束，详见下方「MiniMax Code 与豆包」；遇到 `710010702` 请改用客户端手工签到，不要反复重跑。
* 项目**不会自动更新**，也不建议为它开启自动拉取最新代码：各上游客户端的私有协议随时可能变化，无版本锁定的自动更新会显著放大供应链风险。请固定到带版本号的 tag，并手动升级。
* 仅供个人学习与自动化探索使用，请遵守各平台服务条款。

---

## 💡 为什么需要这个项目？

很多开发者每天都会使用 **WorkBuddy**、**Trae**、**Qoder**、**MiniMax Code**、**豆包** 等 AI 工具。为了维持每天的高速并发请求或获得更多使用额度，需要每天打开客户端挨个点击签到、领积分或开盲盒。

但这些客户端**没有官方网页版签到入口**，传统方式要么人肉每天点一遍，要么依赖笨重的 UI 点击脚本（需要亮屏、解锁，且容易点偏）。

**本项目直接解构客户端的鉴权与签到协议**：

* ⚡ **纯静默 API 协议流**：无需启动客户端界面，电脑不闪烁。
* 🪶 **零外部依赖**：纯 Python 标准库，无需 `pip install`。
* 🔒 **凭据只在本地使用**：读取本机已登录 Session，不上传任何凭据，不设内置密钥；落盘的缓存文件以 `0600` 保存。
* ⏰ **launchd 原生排程**：每天 10:05 / 15:05 / 20:05 静默执行，锁屏照常跑；休眠期间错过的时间点，唤醒后由 launchd 补偿补跑。

---

## 🎁 支持平台与每日权益

| 助手客户端 | 路径与标识 | 自动化功能范围 | 刷新时间 (UTC+8) |
| :--- | :--- | :--- | :--- |
| **WorkBuddy**<br>(腾讯生态) | `/Applications/WorkBuddy.app` | • 每日签到（+100 积分，连续签到累计）<br>• 自动开 Buddy 盲盒<br>• 自动领取 Buddy 旅行礼物<br>• 自动接取成长中心全量活动任务 | 00:00 |
| **Trae CN**<br>(字节跳动) | `/Applications/Trae CN.app` | • 每日签到（+100 积分/额度）<br>• 实时可用额度与消耗回查<br>• 设备指纹自动对齐（抗 9074 限流保护机制） | 00:00 |
| **Qoder CN** | `/Applications/Qoder CN.app`（兼容 `Qoder.app`） | • 每日通用 100 Credits 自动 Claim<br>• 本地钥匙串凭证解密与 Campaign 状态回查 | 10:00 |

---

## 📋 环境与前置要求

1. **操作系统**：macOS 11.0+，Apple Silicon 与 Intel 均可。macOS 13+ 首次注册后台服务时，可能需要在「系统设置 → 通用 → 登录项与扩展」批准。
2. **Python**：系统自带 `/usr/bin/python3` 或 Homebrew Python，3.8+，**无需 pip 依赖**（已在 macOS 27.2 + Python 3.9.6 实测通过）。
3. **客户端状态**：对应 App 已装在 `/Applications/`，且**至少打开并登录过一次**（确保本地已生成合法会话）。
4. **终端会话**：`launchctl` 注册需要在图形登录会话的「终端」里执行；SSH / 某些自动化沙盒会话会失败（见故障排查）。

---

## 🚀 快速开始

```bash
# 0. 建议先固定在带版本号的 tag，而不是直接跟 main
git clone https://github.com/RAyymask/mac-ai-auto-checkin.git
cd mac-ai-auto-checkin
git checkout <tag>            # 例如 v1.1.0

# 1. 纯预览：不写文件、不注册、不发请求
bash install.sh --dry-run

# 2. 确认无误后再安装
bash install.sh
```

`install.sh` 会依次完成：**部署脚本** → **生成并注册 LaunchAgent** → **立即试跑一次**（这一步会发网络请求）。

### 安装选项是三态的，不是一句「安装完成」

脚本结束时会分别报告三个状态，**任一失败都不会被静默吞掉**：

| 状态 | 含义 | 失败时的影响 |
| :--- | :--- | :--- |
| `1/3 文件部署` | `~/.auto-checkin/` 脚本与 `~/Library/LaunchAgents/*.plist` | 后续全部不可用 |
| `2/3 服务注册` | `launchctl bootstrap` 是否成功 | 文件已就位，但**本次会话不会自动签到** |
| `3/3 试跑验证` | 五个客户端本轮签到结果 | 不影响定时服务，可手动重跑 |

退出码：`0` 全部成功，`1` 服务注册失败，`2` 试跑有失败项。注册失败时脚本会打印针对性诊断，并继续完成自检与试跑，**不会假装成功**。

> 去掉了 plist 里的 `RunAtLoad`：原先「注册成功瞬间后台跑一次」与「install.sh 同步跑一次」叠加，会在一次安装里发两轮签到请求。现在只在安装时同步试跑一次，之后完全交给每天三个时间点。

### 其他选项

```bash
bash install.sh --no-run    # 部署 + 注册，但不立即试跑
bash install.sh --check     # 离线自检（doctor），不联网、不读取凭据内容
bash install.sh --help
```

## 🆕 MiniMax Code 与豆包

两者都复用本机客户端登录态，**仍然零第三方依赖、纯 Python 标准库**（豆包的 AES 解密调用 macOS 自带的 `/usr/bin/openssl`）。

| 平台 | 凭据来源 | 签到接口 | 幂等判定 |
| :--- | :--- | :--- | :--- |
| MiniMax Code | `~/.minimax/auth/prod/<region>/mcode-public/auth.json` 的 `accessToken`；`realUserID` 取自 `~/Library/Application Support/MiniMax/minimax-agent-cn-config.json` | `GET /minimax-cloud/api/v1/signin/status` + `POST .../claim`（官方 TUI 同款 md5 签名头） | 7 日面板 `is_today && status==3` |
| 豆包 | `~/Library/Application Support/Doubao/Default/Cookies`；钥匙串 `Doubao Browser Safe Storage` 派生密钥 | `POST /alice/ug/campaign/v3/detail/`（只读）+ `/alice/ug/campaign/landing/checkin/` | 活动详情 `daily_checkin.checked_in_today` |

### ⚠️ 豆包裸接口的风控风险

豆包活动页前端 SDK 会带 `a_bogus` / `msToken` / `web_id` 等签名与设备指纹，本项目的纯 HTTP 请求没有这一层。上游 `auto-signin-kit` 在 2026-11-07 实测：**连续发裸请求会让该会话被置为受限，之后连在客户端手工点签到都会失败，需重装客户端才恢复**。因此做了三道约束：

1. 领取前先查只读的 `v3/detail`，只有确认「今天还没签」才发写请求；只读查询失败就收手。
2. 领取请求每次运行**恰好一次，绝不重试、不补发、事后不复查**（接口本身幂等）。
3. `run_all.py` 有「当天已处理就跳过」守卫（标记 `~/.auto-checkin/.doubao_done`，0600），LaunchAgent 一天三次触发也只打一轮；需要重跑设 `DOUBAO_FORCE=1`。

返回 `710010702 系统错误` 时请**改用豆包客户端手工签到，不要反复重跑**。排查一律先用 `--dry-run`：

```bash
python3 ~/.auto-checkin/minimax_checkin.py --dry-run   # 只查状态，不领取
python3 ~/.auto-checkin/doubao_checkin.py --dry-run    # 只查活动详情，不领取
```

手动覆盖凭据（客户端未登录或凭据读不到时）：

```bash
MINIMAX_ACCESS_TOKEN=... MINIMAX_USER_ID=... python3 ~/.auto-checkin/minimax_checkin.py
DOUBAO_COOKIE='sessionid=...; sid_tt=...; uid_tt=...' python3 ~/.auto-checkin/doubao_checkin.py
DOUBAO_CAMPAIGN_CODE=pc_incentive_task_mvp_v3 python3 ~/.auto-checkin/doubao_checkin.py --dry-run
```

豆包活动换季（返回 `campaign not found`）时更新 `DOUBAO_CAMPAIGN_CODE` 即可。首次读取豆包钥匙串可能弹系统授权框，请在「终端」里手动跑一次 `--dry-run` 并选「始终允许」，之后后台任务才读得到。

> 协议参考：`MiniMax-AI/minimax-code`（官方 TUI 的 `http-gateway.ts` / `public-gateway.ts` / `daily-signin.ts`）、`hiclaw168-163/auto-signin-kit` 的 NOTE-04、`tututashu/doubao-auto-checkin`（MIT，macOS Cookie 解密）、`welldo/QinglongMy`。本项目未复制这些仓库的代码，仅实现其公开的协议契约。

---

## 🛠️ 常用管理指令

| 操作 | 命令 |
| :--- | :--- |
| 手动立即签到 | `~/.auto-checkin/checkin` |
| **离线自检（推荐排障第一步）** | `~/.auto-checkin/checkin doctor` |
| 自检结果转 JSON（供脚本消费） | `~/.auto-checkin/checkin doctor --json` |
| 签到结果转 JSON（不弹通知） | `~/.auto-checkin/checkin --json` |
| 查看日志 | `tail -n 25 ~/.auto-checkin/checkin.log` |
| 查看 launchd 输出 | `tail -f ~/.auto-checkin/launchd.out.log` |
| 查看服务状态 | `launchctl print gui/$(id -u)/com.user.ai-daily-checkin` |
| 卸载（保留脚本与日志） | `bash uninstall.sh` |
| 彻底卸载（删除目录，不可恢复） | `bash uninstall.sh --purge` |

`doctor` 会检查 Python 版本、五个客户端是否安装、脚本完整性与语法、目录/凭据文件权限、`openssl` 与两个新平台的凭据文件是否就位、plist 内容与定时服务注册状态、日志体积，并给出修复命令。它**不联网**，也**不会打印任何 token 内容**。

---

## 🔐 Qoder 钥匙串授权（以及卸载后的撤销）

首次读取 Qoder 桌面端的加密钥匙时，macOS 可能弹窗要求授权：

```bash
python3 ~/.auto-checkin/qoder_signin.py auto
```

输入 Mac 开机密码并点击**「始终允许」(Always Allow)** 后，后台静默运行不再弹窗。

> **重要**：「始终允许」是 macOS 记在钥匙串条目上的系统级 ACL，**卸载脚本不会、也无法自动撤销**。卸载后请打开「钥匙串访问」→ 登录 → 密码类 →「Qoder CN App Safe Storage」→ 双击 →「访问控制」，删除 `python3` 对应条目，或改回「每次询问」。`uninstall.sh` 会再次提示这一点。

---

## 🩺 故障排查

<details>
<summary><code>Bootstrap failed: 5: Input/output error</code></summary>

`launchctl` 拒绝注册时，脚本会保留完整错误到 `~/.auto-checkin/bootstrap.err`。按顺序检查：

1. **是否图形登录会话**：`launchctl managername` 应为 `Aqua`。SSH、后台任务、某些 IDE/自动化沙盒会话会返回 EIO；请在 macOS 自带的「终端」App 里重跑：
   ```bash
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.ai-daily-checkin.plist
   ```
2. **是否已有同名服务**：先用 `launchctl print gui/$(id -u)/com.user.ai-daily-checkin` 查看已注册内容。**不要一上来就 bootout**：`install.sh` 会自动比对已注册 plist 与模板，配置一致且服务正常时保留注册、不会重复 bootstrap；只有确认注册内容确已损坏、需要强制重建时才手动清理后重跑：
   ```bash
   launchctl bootout gui/$(id -u)/com.user.ai-daily-checkin
   bash install.sh
   ```
3. **macOS 13+ 后台项批准**：检查「系统设置 → 通用 → 登录项与扩展」中是否有待批准项。
4. **文件其实已经就位**：plist 位于 `~/Library/LaunchAgents` 且未被禁用时，**重新登录 macOS 后 launchd 通常会自动加载它**。手动注册只是让本次会话立刻生效。
5. 用 `bash install.sh --check` 确认到底是「文件没部署」还是「服务没注册」。

</details>

<details>
<summary>签到返回 <code>NO_AUTH</code> / 客户端未检测到</summary>

* 确认对应 App 已安装在 `/Applications` 且**至少登录过一次**；
* WorkBuddy / Trae 的登录态过期时，重新打开客户端登录一次；
* Qoder 走钥匙串授权，见上一节；
* 单独跑子脚本看详细输出：`python3 ~/.auto-checkin/signin.py auto`、`python3 ~/.auto-checkin/qoder_signin.py auto`。

</details>

<details>
<summary>Homebrew 版 Python 找不到</summary>

`install.sh` 依次探测 `/opt/homebrew/bin/python3`、`/usr/local/bin/python3`、`/usr/bin/python3`，系统自带 Python 完全够用。非登录 shell 未加载 `~/.zprofile` 导致 `brew` 不在 PATH 时不影响安装。

</details>

---

## 💤 熄屏、锁屏与合盖唤醒机制

* **锁屏 / 仅屏幕熄灭**：网络正常，脚本在 10:05 / 15:05 / 20:05 静默完成签到。
* **合盖 / 深度休眠**：休眠期间 CPU 暂停。借助 `launchd` 对 `StartCalendarInterval` 的排程补偿，唤醒后错过的时间点会被补跑。
* **幂等**：已签到会由服务端回查直接跳过，不会重复领取，也不会因多次排程触发风控。

---

## 🔔 通知与日志

每次签到完成后通过 macOS 通知中心推送汇总（消息用分号分隔，AppleScript 不解析 `\n`）：

```text
每日签到助手 · AI 助手积分领取完毕
✅ WorkBuddy: 今日已签 (+100积分)，连签 4 天; ✅ Trae: 今日已完成; ✅ Qoder: 已领今日 100 Credits; ✅ MiniMax Code: 签到成功 +100 积分; ✅ 豆包: 签到成功 +200 额度
```

`checkin.log` 超过 1 MB 会自动轮转成 `checkin.log.1`。`launchd.out.log` / `launchd.err.log` 由 launchd 直接写入，无法在脚本内安全轮转，`doctor` 会在它们超过 1 MB 时提示手动清理。

---

## 🔒 安全与隐私说明

* 部署目录 `~/.auto-checkin` 权限 `0700`；脚本、`checkin` 命令与 plist 均仅当前用户可读写。
* `.trae_token_cache.json`、`trae-*.json`、state / device-id 文件里的 `refreshToken` 属于明文凭据，统一通过 `0600` 原子写入；安装时会把历史遗留的宽松权限一并收紧。
* 子脚本输出经过脱敏（`[REDACTED]`）；`doctor` 只报告文件权限，**不读取也不打印凭据内容**。
* 结果解析由 `checkin_protocol.py` 统一归一化，子脚本保留原有输出格式以兼容上游项目；Trae 额外输出一行 `__CHECKIN__ {json}` 机器可读结果。
* 请求仅指向官方域名：`copilot.tencent.com`、`api.trae.cn`、`api.trae.com.cn`、`openapi.qoder.com.cn`。企业微信 / PushPlus 推送 token 从环境变量读取，默认关闭，无硬编码回传地址。

---

## 📌 版本与校验（维护者建议）

发布时请打 tag 并附 SHA-256，用户安装前可校验，避免直接跟随 `main`：

```bash
git checkout v1.1.0
shasum -a 256 install.sh scripts/*.py
```

本项目**不提供也不建议启用自动更新**：读的是私有协议，客户端更新随时可能导致脚本失效；固定版本 + 人工升级更安全。

---

## 🤝 致谢与开源参考

感谢开源社区先驱的逆向分析与脚本实践，本项目在开发过程中借鉴了以下优秀的开源成果：

* [88lin / workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin)
* [L0NE-6 / Trae-AutoCheckin](https://github.com/L0NE-6/Trae-AutoCheckin)
* [L0NE-6 / WorkBuddy-Daily](https://github.com/L0NE-6/WorkBuddy-Daily)

---

## 📄 开源许可证

本项目基于 [MIT 许可证](LICENSE) 开源。仅供个人学习与自动化探索使用，请遵守各平台的服务条款。
