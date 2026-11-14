# 🍎 mac-ai-auto-checkin

<p align="center">
  <strong>专为 macOS 打造的 AI 办公与编程助手每日自动一键签到 & 积分领取套件</strong><br>
  <strong>5 个平台</strong>：<strong>WorkBuddy</strong> (腾讯) · <strong>Trae CN</strong> (字节跳动) · <strong>Qoder CN</strong><br>
  <strong>MiniMax Code</strong> (MiniMax) · <strong>豆包</strong> (字节跳动)<br>
  纯 Python 标准库 · 无需启动客户端 · launchd 静默排程
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-macOS%2011.0%2B-black?logo=apple&style=flat-square" alt="macOS">
  <img src="https://img.shields.io/badge/Arch-Apple%20Silicon%20%7C%20Intel-blue?style=flat-square" alt="Architecture">
  <img src="https://img.shields.io/badge/Python-3.8%2B%20(Zero--Dep)-3776AB?logo=python&logoColor=white&style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/Scheduler-macOS%20launchd-007AFF?style=flat-square" alt="launchd">
  <img src="https://img.shields.io/badge/Clients-5%20platforms-orange?style=flat-square" alt="5 platforms">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

---

## ⚠️ 使用前必读

* **本项目调用的是各客户端的未公开接口**，并非官方签到入口（唯一例外：MiniMax 官方 TUI 自带 `/checkin`，本项目复刻其签名协议以便静默执行）。自动化领取积分、Trae 的设备指纹对齐逻辑，以及豆包绕过前端签名的裸请求，都可能违反对应平台的服务条款，存在账号或会话被限制的风险。请自行评估。
* **默认安装 (`bash install.sh`) 会立即使用你本机已登录的账号，向五个平台发送签到请求**。只想准备文件、不发起任何请求，请用 `--dry-run`（纯预览）或 `--no-run`（部署+注册但不试跑）。
* 安装过程会**读取本机客户端的登录态**，Qoder 与豆包部分还会读取 macOS 钥匙串（`Doubao Browser Safe Storage`）。首次可能弹出系统授权对话框，请在「终端」里手动跑一次并选「始终允许」；后台任务读不到时会明确报 `NO_AUTH`，不会静默失败。
* **豆包走的是未签名裸 HTTP 接口**：上游实测连续请求可能让整个会话被降权，连客户端手工签到都会失效（2026-11-13 本机实测确认）。项目已加「当天无论成功失败只跑一次 + 写请求绝不重试」的约束，并可随时用 `DOUBAO_DISABLE=1` 完全停用，详见下方「MiniMax Code 与豆包」；遇到 `710010702` **不要反复重跑**，先停用自动请求再手工签到；若客户端手工签到也失败，说明会话已被置为受限，需退出重登或重装客户端。
* 项目**不会自动更新**，也不建议为它开启自动拉取最新代码：各上游客户端的私有协议随时可能变化，无版本锁定的自动更新会显著放大供应链风险。请固定到带版本号的 tag，并手动升级。
* 仅供个人学习与自动化探索使用，请遵守各平台服务条款。

---

## 💡 为什么需要这个项目？

很多开发者每天都会使用 **WorkBuddy**、**Trae**、**Qoder**、**MiniMax Code**、**豆包** 等 AI 工具。为了维持每天的高速并发请求或获得更多使用额度，需要每天打开客户端挨个点击签到、领积分或开盲盒。

但多数客户端**没有官方网页版签到入口**（MiniMax 的签到命令只存在于 TUI 内），传统方式要么人肉每天点一遍，要么依赖笨重的 UI 点击脚本（需要亮屏、解锁，且容易点偏）。

**本项目直接解构客户端的鉴权与签到协议**：

* ⚡ **纯静默 API 协议流**：无需启动客户端界面，电脑不闪烁。
* 🪶 **零 pip 依赖**：纯 Python 标准库，无需 `pip install`；豆包的 Cookie 解密调用 macOS 自带的 `/usr/bin/openssl`，不装 Playwright、不装浏览器。
* 🔒 **凭据只在本地使用**：读取本机已登录 Session，不上传任何凭据，不设内置密钥；落盘的缓存文件以 `0600` 保存。
* ⏰ **双 LaunchAgent 排程**：日历服务每天 10:05 / 15:05 / 20:05 静默执行；独立的「开机补签」服务在每次登录后检查当天是否已签到，缺则补跑 —— **关机期间错过的轮次不再漏签**（2026-11-14 实测修复）。
* 🛡️ **风控感知**：每个平台都先查状态再决定是否领取；豆包额外限制「每天最多一轮、写请求恰好一次」，详见下方专章。

---

## 🎁 支持平台与每日权益

| 助手客户端 | 路径与标识 | 自动化功能范围 | 刷新时间 (UTC+8) |
| :--- | :--- | :--- | :--- |
| **WorkBuddy**<br>(腾讯生态) | `/Applications/WorkBuddy.app` | • 每日签到（+100 积分，连续签到累计）<br>• 自动开 Buddy 盲盒<br>• 自动领取 Buddy 旅行礼物<br>• 自动接取成长中心全量活动任务 | 00:00 |
| **Trae CN**<br>(字节跳动) | `/Applications/Trae CN.app` | • 每日签到（+100 积分/额度）<br>• 实时可用额度与消耗回查<br>• 设备指纹自动对齐（抗 9074 限流保护机制） | 00:00 |
| **Qoder CN** | `/Applications/Qoder CN.app`（兼容 `Qoder.app`） | • 每日通用 100 Credits 自动 Claim<br>• 本地钥匙串凭证解密与 Campaign 状态回查 | 10:00 |
| **MiniMax Code**<br>(MiniMax) | `/Applications/MiniMax Code.app`<br>凭据：`~/.minimax/auth/` | • 7 日签到面板状态回查 + 自动领取（实测 +400 积分/日）<br>• 读取客户端 `accessToken`（OAuth2 opaque token）；**CN 区默认不发必然 401 的 renewal**<br>• 签到前自动判断 token 是否临近过期，必要时**自行启动客户端**刷新登录态（无需人工打开）<br>• 复刻官方 TUI 的 `status` / `claim` 签名协议<br>• 连签天数与当日积分可读诊断 | 以服务端 7 日面板为准 |
| **豆包**<br>(字节跳动) | `/Applications/Doubao.app`<br>凭据：`.../Doubao/Default/Cookies` | • 活动详情只读查询 + 签到领额度（实测 +200 额度）<br>• **当天已处理守卫**，一天三次排程也只打一轮<br>• 活动码可配置，换季无需改代码 | 以活动页为准 |

> 表中积分/额度为 2026-11-08 实测值，实际发放以各平台官方活动规则为准，可能随时调整。新增两个平台的凭据、接口与风控说明见「MiniMax Code 与豆包」章节。

---

## 📋 环境与前置要求

1. **操作系统**：macOS 11.0+，Apple Silicon 与 Intel 均可。macOS 13+ 首次注册后台服务时，可能需要在「系统设置 → 通用 → 登录项与扩展」批准。
2. **Python**：系统自带 `/usr/bin/python3` 或 Homebrew Python，3.8+，**无需 pip 依赖**（已在 macOS 27.2 + Python 3.9.6 实测通过）。
3. **openssl**：豆包 Cookie 解密需要 `/usr/bin/openssl`（macOS 自带；缺失时安装 Xcode Command Line Tools）。`doctor` 会静态检查其存在性。
4. **客户端状态**：对应 App 已装在 `/Applications/`，且**至少打开并登录过一次**（确保本地已生成合法会话）。豆包需在登录后**退出一次客户端**让 Cookie 落盘；MiniMax 也可通过官方 CLI 登录生成 `~/.minimax/auth/`。未安装的平台会在 `doctor` 里标红，不影响其他平台。
5. **终端会话**：`launchctl` 注册需要在图形登录会话的「终端」里执行；SSH / 某些自动化沙盒会话会失败（见故障排查）。

---

## 🚀 快速开始

```bash
# 0. 建议先固定在带版本号的 tag，而不是直接跟 main
git clone https://github.com/RAyymask/mac-ai-auto-checkin.git
cd mac-ai-auto-checkin
git checkout <tag>            # 例如 v1.2.0（发布后）；也可用某个 commit SHA 固定

# 1. 纯预览：不写文件、不注册、不发请求
bash install.sh --dry-run

# 2. 确认无误后再安装
bash install.sh
```

`install.sh` 会依次完成：**部署脚本** → **生成并注册日历 LaunchAgent** → **立即试跑一次**（这一步会向五个平台发网络请求）→ **注册开机补签 LaunchAgent**。两个服务的分工见下一节。

> 首次安装建议先跑两个新平台的 `--dry-run`（只读、不领取），确认凭据与签名都通了再执行默认安装；豆包尤其不建议在状态不明时反复重跑。

### 安装选项是三态的，不是一句「安装完成」

脚本结束时会分别报告三个阶段的状态（**不是三个平台**），**任一失败都不会被静默吞掉**：

| 状态 | 含义 | 失败时的影响 |
| :--- | :--- | :--- |
| `1/3 文件部署` | `~/.auto-checkin/` 脚本与 `~/Library/LaunchAgents/*.plist` | 后续全部不可用 |
| `2/3 服务注册` | `launchctl bootstrap` 是否成功 | 文件已就位，但**本次会话不会自动签到** |
| `3/3 试跑验证` | 五个平台本轮签到结果（豆包命中当日守卫时显示「今日已处理，跳过」） | 不影响定时服务，可手动重跑 |

退出码：`0` 全部成功，`1` 服务注册失败，`2` 试跑有失败项。注册失败时脚本会打印针对性诊断，并继续完成自检与试跑，**不会假装成功**。

### 🔁 开机补签：关机也不会漏签

`launchd` 的 `StartCalendarInterval` **只在系统运行时触发**；关机期间错过的 10:05 / 15:05 / 20:05 不会被补跑。2026-11-14 实测：11-13 23:41 关机、11-14 15:32 才登录，当天前两轮全部漏掉，直到人工补跑才签到。

为此项目注册 **两个** LaunchAgent：

| 服务 | 触发方式 | 作用 |
| :--- | :--- | :--- |
| `com.user.ai-daily-checkin` | 每天 10:05 / 15:05 / 20:05 | 常规静默签到（**不设 `RunAtLoad`**） |
| `com.user.ai-daily-checkin.catchup` | 仅在 launchd 加载瞬间（`RunAtLoad`） | 登录后检查当天是否已有一轮完整签到，缺则补跑 |

为什么是两个服务：同一个 plist 的 `ProgramArguments` 无法区分「加载触发」与「日历触发」。若把「当天已签就跳过」的守卫塞进 `run_all.py`，每天后两轮会被误判成重复而跳过，反而丢掉补签机会。

`catchup.py` 的流程：**等网络就绪**（默认最多 30 秒，`AUTO_CHECKIN_CATCHUP_NETWORK_WAIT=0` 可跳过）→ 读 `checkin.log` 统计当天「启动标记 → 结束分隔符」的完整轮次 → 已有则写一行日志、零请求退出，否则调用 `run_all.py`。半途崩溃的轮次没有结束分隔符，不会被误判成已完成。它**继承主服务 plist 的 `EnvironmentVariables`**，所以 `DOUBAO_DISABLE=1` 之类的本机停用配置同样生效。

安装顺序也刻意安排过：先同步试跑写好当天日志，再注册补签服务，这样 `RunAtLoad` 触发时会直接跳过，**一次安装不会发两轮请求**；`--no-run` 则只写入补签 plist、不注册，避免「说好不试跑、结果加载瞬间反而跑了一轮」。可用 `python3 ~/.auto-checkin/catchup.py --dry-run` 零请求预览它会做什么，`--force` 可强制补跑。

### 其他选项

```bash
bash install.sh --no-run    # 部署 + 注册日历服务，不立即试跑；补签 plist 只写入不注册
bash install.sh --check     # 离线自检（doctor），不联网、不读取凭据内容
bash install.sh --help
```

---

## 🆕 MiniMax Code 与豆包

两者都复用本机客户端登录态，**仍然零第三方依赖、纯 Python 标准库**（豆包的 AES 解密调用 macOS 自带的 `/usr/bin/openssl`，不是 Python 包）。新增脚本为 `scripts/minimax_checkin.py` 与 `scripts/doubao_checkin.py`，`install.sh` 通配部署 `scripts/*.py`，升级时会自动带上。

已于 2026-11-08 在本机实跑验证：MiniMax Code「今日已签到 +400 积分（第 1 天）」、豆包「今日已签到 +200 额度（连签 1 天）」。两者都命中幂等，**没有发出任何领取写请求**。

> 2026-11-12 修复了两处长期失效：豆包失败时不写当天标记，导致 `710010702` 被 launchd 一天重复打三次；MiniMax 本地 `expiresAtMs` 硬拦截导致连续 13 轮误判过期。另于 2026-11-13 查清 CN 区 renewal 属协议错配并默认关闭，并新增「签到前自动启动客户端刷新登录态」，见「登录态与『续期』坑」。

| 平台 | 凭据来源 | 签到接口 | 幂等判定 |
| :--- | :--- | :--- | :--- |
| MiniMax Code | `~/.minimax/auth/prod/<region>/mcode-public/auth.json` 的 `accessToken`；续期后的 token 存 `~/.auto-checkin/.minimax_token.json`（0600）；`realUserID` 取自 `~/Library/Application Support/MiniMax/minimax-agent-cn-config.json` | `POST /v1/api/user/renewal`（先续期）→ `GET /minimax-cloud/api/v1/signin/status` → `POST .../claim`（官方 TUI 同款 md5 签名头）；CN `agent.minimaxi.com`，国际区 `agent.minimax.io` | 7 日面板 `is_today && status==3`；领取返回 `claim_result=2` 也视为今日已领 |
| 豆包 | `~/Library/Application Support/Doubao/Default/Cookies`；钥匙串 `Doubao Browser Safe Storage` 派生密钥，用 `openssl` 解 AES-128-CBC | `POST /alice/ug/campaign/v3/detail/`（POST 方法，语义只读）+ `POST /alice/ug/campaign/landing/checkin/`，域名 `www.doubao.com` | 活动详情 `tasks[].campaign_code=="daily_signin"` 下的 `daily_checkin.checked_in_today` |

### ⚠️ 豆包裸接口的风控风险

豆包活动页前端 SDK 会带 `a_bogus` / `msToken` / `web_id` 等签名与设备指纹，本项目的纯 HTTP 请求没有这一层。上游 `auto-signin-kit` 在 2026-11-07 实测：**连续发裸请求会让该会话被置为受限，之后连在客户端手工点签到都会失败，需重装客户端才恢复**；2026-11-13 本机用 GUI 实点「立即签到」复现了「签到失败，请稍后重试」，确认这不是脚本缺签名的问题，而是账号会话本身被降权。因此做了三道约束：

1. 领取前先查只读的 `v3/detail`，只有确认「今天还没签」才发写请求；只读查询失败就收手。
2. 领取请求每次运行**恰好一次，绝不重试、不补发、事后不复查**（接口本身幂等）。
3. `run_all.py` 有「当天已执行就跳过」守卫（标记 `~/.auto-checkin/.doubao_done`，0600）：**无论成功、幂等、鉴权失败还是 `710010702`，只要脚本跑过一次就标记当天**，LaunchAgent 一天三次触发也只打一轮。失败时更要熔断，否则正是上游警告的「连续裸请求」路径。需要重跑设 `DOUBAO_FORCE=1`；想彻底停掉该平台设 `DOUBAO_DISABLE=1`（不发送任何请求，也不影响其他四个平台）。

返回 `710010702 系统错误` 时请**先设 `DOUBAO_DISABLE=1` 停掉自动请求，再改用豆包客户端手工签到，不要反复重跑**（会话已被置为受限时，客户端内手工签到也可能失败，见故障排查）。排查一律先用 `--dry-run`：

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

| 环境变量 | 默认值 | 用途 |
| :--- | :--- | :--- |
| `MINIMAX_ACCESS_TOKEN` / `MINIMAX_USER_ID` | 读 `~/.minimax/auth/` 与客户端配置 | 手动注入 MiniMax 登录态（优先级最高）；缺 `user_id` 会被网关判 401 |
| `MINIMAX_REGION` | `cn` | `cn` → `agent.minimaxi.com`，`en` → `agent.minimax.io` |
| `MINIMAX_RENEW` | CN 区 `0`、国际区 `1` | 设为 `1` 强制启用 `/v1/api/user/renewal`，`0` 强制关闭；CN 区启用必然 401，仅用于排查 |
| `MINIMAX_NO_LAUNCH` | 未设置 | 设为 `1` 完全停用「签到前自动启动 MiniMax Code 客户端」 |
| `MINIMAX_LAUNCH_MARGIN_MIN` | `180` | 客户端 token 剩余不足该分钟数就自动启动刷新；仅用于排查 |
| `DOUBAO_COOKIE` | 读客户端 Cookie 库 | 手动注入 `sessionid` / `sid_tt` / `uid_tt` 三项，缺一即报 `NO_AUTH` |
| `DOUBAO_CAMPAIGN_CODE` | `pc_incentive_task_mvp_v3` | 活动码，换季时更新 |
| `DOUBAO_CLIENT_UA_VERSION` | `2.33.3` | UA 中的客户端版本号 |
| `DOUBAO_FORCE` | 未设置 | 设为 `1` 绕过「当天已执行」守卫强制重跑（`run_all.py` 读取） |
| `DOUBAO_DISABLE` | 未设置 | 设为 `1` 完全停用豆包自动签到，`run_all.py` 不发任何请求 |

两个脚本都支持 `--dry-run`（只查状态，绝不领取）与 `--json`（兼容参数，输出本就是结构化结果）。豆包活动换季（返回活动不在期 / `campaign not found`）时更新 `DOUBAO_CAMPAIGN_CODE` 即可。首次读取豆包钥匙串可能弹系统授权框，请在「终端」里手动跑一次 `--dry-run` 并选「始终允许」，之后后台任务才读得到。

> 协议参考：`MiniMax-AI/minimax-code`（官方 TUI 的 `http-gateway.ts` / `public-gateway.ts` / `daily-signin.ts`）、`hiclaw168-163/auto-signin-kit` 的 NOTE-04、`tututashu/doubao-auto-checkin`（MIT，macOS Cookie 解密）、`welldo/QinglongMy`、`VICqiufeeng/dsh-minimax-connect`（CN 区 OAuth2 续期实测契约）。本项目未复制这些仓库的代码，仅实现其公开的协议契约。

---

### 🔄 MiniMax Code 的登录态与「续期」坑

CN 区桌面端是标准 OAuth2：`~/.minimax/auth/prod/cn/mcode-public/auth.json` 里同时存 `accessToken`（`mmoat_…`）与 `refreshToken`（`mmort_…`），都是 60 字符 opaque token，**不是 JWT**；`expiresAtMs` 实测约 12 小时，由客户端启动时自行刷新。

| | 国际区 / 旧版桌面端 | CN 区桌面端（本机） |
| :--- | :--- | :--- |
| 凭据 | `minimax-agent-config.json` 里的 HS256 JWT | `auth.json` 的 `mmoat_` / `mmort_` |
| 域名 | `agent.minimax.io` | 签到 `agent.minimaxi.com`；OAuth `account.minimax.cn` |
| 续期 | `POST /v1/api/user/renewal` + `token:` 头 → `data.token` 新 JWT | `POST /oauth2/token`，`grant_type=refresh_token` + `client_id=mcode-public` + `audience=agent-backend` |
| 轮换 | 旧 token 换新 token，顺延约 40 天 | `refresh_token` **单次使用、每次轮换**，须原子回写 `auth.json` + `auth-state.json` 并递增 `generation` |

**根因**：早期版本把 `welldo/QinglongMy` 的 renewal 直接搬过来，用 CN 的 `accessToken` 当 `token:` 头去打 `agent.minimaxi.com/v1/api/user/renewal`。端点、鉴权头、凭据类型三处都不属于同一体系，所以**即使 token 有效也恒定返回 `401 登陆失败`**——不是登录过期、不是签名错、不是服务端故障，而是协议错配（换 `refreshToken` 当头同样无效，2026-11-12 实测）。

**已落地修复（2026-11-13）**：CN 区默认不再发这个必然失败的 POST，直接用客户端 `auth.json` 的 `accessToken` 走 `status` → `claim`；国际区仍默认启用 renewal。开关：`MINIMAX_RENEW=1` 强制开启、`MINIMAX_RENEW=0` 强制关闭，`--renew` 显式探测，`--dry-run` 严格零写请求。签到本身从未受影响（本机实测 +400 积分正常）。

> **2026-11-13 00:49 实跑复验**：`DOUBAO_DISABLE=1 ~/.auto-checkin/checkin --json` 返回 `ok:true` —— WorkBuddy +100（连签 17 天）、Trae +100（当前 5900）、Qoder 今日已领、MiniMax +400（第 2 天）、豆包 `SKIP 已停用（本轮不发送任何请求）`。单独跑 `minimax_checkin.py --json` 明确输出 `[MiniMax] 按 region 跳过 renewal`，复跑返回 `ALREADY / renewed:false`，且未生成 `.minimax_token.json`：确认 CN 区确实不再发续期 POST、签到幂等正常。
>
> **2026-11-13 19:08 / 19:12 自动启动实跑**：当天 10:51 token 过期，15:05 那轮 MiniMax 报 401；19:08 执行 `/usr/bin/open -a "MiniMax Code"`，2 秒内 `auth.json` 的 `expiresAtMs` 从 10:51 顺延到次日 07:08。随后完整签到 `ok:true`（四平台 `ALREADY`、豆包 `SKIP`）。「过期 → 启动 → 刷新」与「token 新鲜 → 不启动、无需刷新」两条路径均已实测。

**为什么不去「修好」CN 续期**：正确实现要拿 `refreshToken` 换 token，而它一次性轮换，必须同时原子回写客户端的 `auth.json`、`auth-state.json` 并同步 `generation` 与文件锁，否则桌面端会把自己的新 token 判成「已登出」、用户被迫重新扫码登录。为省一次客户端启动而去改写登录态，风险与收益完全不成比例。因此本项目**只读取、不接管**客户端的 OAuth 刷新。

**token 过期怎么办（2026-11-13 起已自动化）**：CN 区签到前会读 `auth.json` 的 `expiresAtMs`，剩余不足 **180 分钟**或已过期时，自行执行 `/usr/bin/open -a "MiniMax Code"` 启动客户端，轮询最多 20 秒等它刷新，再重新读凭据签到。每天 10:05 那轮自动启动一次，就能覆盖当天 10:05 / 15:05 / 20:05 三轮，不再出现下午 401。签到结果里会带 `client_launched` 字段，日报里也会写明「已自行启动 MiniMax Code」。

约束与边界：

* `--dry-run` / `--renew` 保持零副作用，不启动客户端；用 env 注入凭据或国际区 renewal 缓存为首选时也不启动（不需要 GUI）。
* `MINIMAX_NO_LAUNCH=1` 完全停用；`MINIMAX_LAUNCH_MARGIN_MIN` 调整阈值（默认 180 分钟，仅用于排查）。
* 客户端 token 仍有效时，启动后它判断「无需刷新」就不会改写 `auth.json`，这是正常行为，脚本会如实记录并继续签到。
* 脚本**只启动、不退出 / 重启正在运行的客户端**，也绝不改写客户端登录态文件。若客户端本就已运行且 token 已过期，激活不会触发刷新，此时请手动退出并重新打开一次客户端，或设 `MINIMAX_ACCESS_TOKEN` / `MINIMAX_USER_ID`。
* CN 区不需要跑 `--renew`（预期就是 401）。

---

## 🛠️ 常用管理指令

| 操作 | 命令 |
| :--- | :--- |
| 手动立即签到（五个平台） | `~/.auto-checkin/checkin` |
| 只查 MiniMax 状态，不领取 | `python3 ~/.auto-checkin/minimax_checkin.py --dry-run` |
| 探测 renewal 端点（CN 区预期 401） | `python3 ~/.auto-checkin/minimax_checkin.py --renew` |
| 强制启用 / 关闭 renewal（排查用） | `MINIMAX_RENEW=1 ~/.auto-checkin/checkin` / `MINIMAX_RENEW=0 ~/.auto-checkin/checkin` |
| 停用 / 调整「自动启动客户端」 | `MINIMAX_NO_LAUNCH=1 ~/.auto-checkin/checkin` / `MINIMAX_LAUNCH_MARGIN_MIN=60 ~/.auto-checkin/checkin` |
| 只查豆包活动详情，不领取 | `python3 ~/.auto-checkin/doubao_checkin.py --dry-run` |
| 强制重跑豆包（绕过当天守卫） | `DOUBAO_FORCE=1 ~/.auto-checkin/checkin` |
| 临时停用豆包（会话受限时用） | `DOUBAO_DISABLE=1 ~/.auto-checkin/checkin` |
| **离线自检（推荐排障第一步）** | `~/.auto-checkin/checkin doctor` |
| 自检结果转 JSON（供脚本消费） | `~/.auto-checkin/checkin doctor --json` |
| 签到结果转 JSON（不弹通知） | `~/.auto-checkin/checkin --json` |
| 查看日志 | `tail -n 25 ~/.auto-checkin/checkin.log` |
| 查看 launchd 输出 | `tail -f ~/.auto-checkin/launchd.out.log` |
| 查看服务状态 | `launchctl print gui/$(id -u)/com.user.ai-daily-checkin` |
| 查看开机补签服务状态 | `launchctl print gui/$(id -u)/com.user.ai-daily-checkin.catchup` |
| 预览开机补签会做什么（零请求） | `python3 ~/.auto-checkin/catchup.py --dry-run` |
| 手动补跑一轮（绕过当天守卫） | `python3 ~/.auto-checkin/catchup.py --force` |
| 查看开机补签日志 | `tail -f ~/.auto-checkin/launchd.catchup.log` |
| 手动注册开机补签服务 | `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.ai-daily-checkin.catchup.plist` |
| 卸载（保留脚本与日志） | `bash uninstall.sh` |
| 彻底卸载（删除目录，不可恢复） | `bash uninstall.sh --purge` |

`doctor` 逐项检查 Python 版本、五个客户端是否安装、10 个脚本的完整性与语法、目录与凭据缓存权限（含 MiniMax 续期缓存，存在时才检查）、`openssl` 是否可用、豆包 Cookie 库与 MiniMax `auth.json` 是否就位、**两个 LaunchAgent** 的配置与注册状态（含补签服务是否继承 `EnvironmentVariables`）、日志体积，并给出修复命令。它**不联网**，也**不会读取或打印任何凭据内容**。

---

## 🔐 钥匙串授权（Qoder / 豆包，以及卸载后的撤销）

两个平台需要读 macOS 钥匙串，首次可能弹窗要求授权：

```bash
# Qoder：桌面端加密钥匙
python3 ~/.auto-checkin/qoder_signin.py auto
# 豆包：Cookie 解密密钥（--dry-run 只查状态，不会领取）
python3 ~/.auto-checkin/doubao_checkin.py --dry-run
```

输入 Mac 开机密码并点击**「始终允许」(Always Allow)** 后，后台静默运行不再弹窗。涉及的钥匙串条目：

| 平台 | 钥匙串条目 (service) |
| :--- | :--- |
| Qoder CN | `Qoder CN App Safe Storage` |
| 豆包 | `Doubao Browser Safe Storage`（回退 `Doubao Safe Storage`） |

> 某些自动化 / IDE 沙盒会话读钥匙串会间歇性超时并报 `NO_AUTH`，这不是脚本故障：在 macOS 自带的「终端」App 里手动跑一次上面的命令并选「始终允许」即可。

> **重要**：「始终允许」是 macOS 记在钥匙串条目上的系统级 ACL，**卸载脚本不会、也无法自动撤销**。卸载后请打开「钥匙串访问」→ 登录 → 密码类 → 对应条目 → 双击 →「访问控制」，删除 `python3` / `security` 相关条目，或改回「每次询问」。`uninstall.sh` 会再次提示这一点。

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
<summary>关机后当天没签到 / 开机补签服务未注册</summary>

* 关机期间 `StartCalendarInterval` 不会补跑，这是 `launchd` 的既定行为，不是脚本故障。
* 先确认补签服务在册：`launchctl print gui/$(id -u)/com.user.ai-daily-checkin.catchup`。若提示找不到服务，在**图形界面的「终端」**里注册（助手沙盒会返回 EIO）：

  ```bash
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.ai-daily-checkin.catchup.plist
  ```

  或者**重新登录一次 macOS**，launchd 通常会自动加载 `~/Library/LaunchAgents` 下的 plist。
* 用 `python3 ~/.auto-checkin/catchup.py --dry-run` 零请求预览它的判断；想立刻补一轮用 `~/.auto-checkin/checkin`（各平台幂等）或 `python3 ~/.auto-checkin/catchup.py --force`。
* 补签服务必须继承主 plist 的 `EnvironmentVariables`；`install.sh` 重装时会自动合并。若手工改了主 plist 的 `DOUBAO_DISABLE`，记得重跑一次 `bash install.sh --no-run` 让补签 plist 同步。

</details>

<details>
<summary>签到返回 <code>NO_AUTH</code> / 客户端未检测到</summary>

* 确认对应 App 已安装在 `/Applications` 且**至少登录过一次**；
* WorkBuddy / Trae 的登录态过期时，重新打开客户端登录一次；
* Qoder / 豆包走钥匙串授权，见上一节；豆包还需退出一次客户端让 Cookie 落盘；
* MiniMax Code：打开一次客户端让 `auth.json` 刷新即可（CN 区不需要 `--renew`，该端点预期 401）；返回 401/403 也可能是 `realUserID` 缺失或 `MINIMAX_REGION` 不对；
* 单独跑子脚本看详细输出：
  ```bash
  python3 ~/.auto-checkin/signin.py auto
  python3 ~/.auto-checkin/qoder_signin.py auto
  python3 ~/.auto-checkin/minimax_checkin.py --dry-run
  python3 ~/.auto-checkin/doubao_checkin.py --dry-run
  ```

</details>

<details>
<summary>豆包返回 <code>710010702 系统错误</code> / 活动不在期</summary>

* `710010702`：多为裸请求缺少 `a_bogus` 等前端签名导致会话被判异常，也可能是服务端故障。**不要反复重跑脚本**，先设 `DOUBAO_DISABLE=1` 停掉自动请求，再在客户端手工签到。
* **客户端内点「立即签到」也提示「签到失败，请稍后重试」**：说明账号会话已被置为受限，不是脚本缺签名；GUI 自动化或重放签名都无法绕过。请退出豆包账号重新登录，仍失败则完全退出并重装客户端（上游实测），恢复前保持 `DOUBAO_DISABLE=1`。2026-11-13 本机 GUI 实测复现。
* 活动不在期（`campaign not found`）：活动换季了，更新 `DOUBAO_CAMPAIGN_CODE` 后先用 `--dry-run` 验证。
* 出现「今日已处理，跳过」是**预期行为**（当天守卫），确需重跑才设 `DOUBAO_FORCE=1`。
* 会话已被限制时建议先设 `DOUBAO_DISABLE=1` 完全停掉自动请求，只保留其他四个平台，待客户端手工签到恢复正常后再取消；需要长期停用可把该变量写进 LaunchAgent plist 的 `EnvironmentVariables`，再执行 `launchctl bootout gui/$(id -u)/com.user.ai-daily-checkin` 与 `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.ai-daily-checkin.plist` 重新加载（环境变量在加载时读入，改文件不会自动生效）。`install.sh` 重装时会保留这份本机定制。

</details>

<details>
<summary>MiniMax Code 返回 401 / 签到面板查不到</summary>

* 401/403：`user_id` 缺失会直接被网关拒绝，确认客户端配置里有 `sharedUser.realUserID`。
* **token 过期**：`auth.json` 的 `accessToken` 约 12 小时有效期，只在桌面端启动时刷新。CN 区**默认不发 renewal**（该端点属国际区 JWT 协议，恒定 401，详见「登录态与『续期』坑」）；2026-11-13 起脚本会在签到前**自行启动客户端**刷新，无需人工打开。若日志显示 `客户端已启动，但 20 秒内未刷新已过期的 auth.json`，多半是客户端本就已运行（激活不触发刷新），请手动退出重开一次，或设 `MINIMAX_ACCESS_TOKEN` / `MINIMAX_NO_LAUNCH=1` 停用自动启动。
* 想确认是不是续期环节的问题：`--dry-run` 只发一个只读 `status`（不发 renewal / claim）；`MINIMAX_RENEW=1` 可强制启用 renewal 观察报错。
* 国际区用户设 `MINIMAX_REGION=en`（域名 `agent.minimax.io`），renewal 默认开启。

</details>

<details>
<summary>Homebrew 版 Python 找不到</summary>

`install.sh` 依次探测 `/opt/homebrew/bin/python3`、`/usr/local/bin/python3`、`/usr/bin/python3`，系统自带 Python 完全够用。非登录 shell 未加载 `~/.zprofile` 导致 `brew` 不在 PATH 时不影响安装。

</details>

---

## 💤 熄屏、锁屏与合盖唤醒机制

* **锁屏 / 仅屏幕熄灭**：网络正常，日历服务在 10:05 / 15:05 / 20:05 静默完成签到。
* **合盖 / 深度休眠**：休眠期间 CPU 暂停；`launchd` 对 `StartCalendarInterval` 有唤醒补偿，唤醒后可能补跑错过的时间点，但**不保证每次**。
* **关机 / 重启**：**关机期间错过的排程 launchd 完全不会补跑**（2026-11-14 实测两轮全漏）。此时由 `RunAtLoad` 的开机补签服务在登录后检查当天日志，缺则补跑一轮，详见「开机补签」一节。
* **幂等**：所有平台都先回查状态，已签到直接跳过、不会重复领取；豆包额外有本地 `.doubao_done` 守卫，launchd 一天三次补跑也只发一轮请求，避免累积裸请求触发风控。

---

## 🔔 通知与日志

每次签到完成后通过 macOS 通知中心推送汇总（消息用分号分隔，AppleScript 不解析 `\n`）：

```text
每日签到助手 · AI 助手积分领取完毕
✅ WorkBuddy: 今日已签 (+100积分)，连签 4 天，累计 1200; ✅ Trae: 今日已完成; ✅ Qoder: 已领今日 100 Credits; ✅ MiniMax Code: 今日已签到 +400 积分（第 1 天）; ✅ 豆包: 今日已签到 +200 额度（连签 1 天）
```

> 以上为示例文本，积分/额度数值来自服务端实时返回，会随官方活动调整。

`checkin.log` 超过 1 MB 会自动轮转成 `checkin.log.1`。`launchd.out.log` / `launchd.err.log` / `launchd.catchup.log` 由 launchd 直接写入，无法在脚本内安全轮转，`doctor` 会在主日志超过 1 MB 时提示手动清理；`catchup.py` 自己的判断与结果也会写进 `checkin.log`，前缀 `[Catchup]`。

---

## 🔒 安全与隐私说明

* 部署目录 `~/.auto-checkin` 权限 `0700`；脚本、`checkin` 命令与 plist 均仅当前用户可读写。
* `.trae_token_cache.json`、`trae-*.json`、state / device-id 文件里的 `refreshToken` 属于明文凭据，统一通过 `0600` 原子写入；安装时会把历史遗留的宽松权限一并收紧。
* 子脚本输出经过脱敏（`[REDACTED]`）；`doctor` 只报告文件权限，**不读取也不打印凭据内容**。
* 结果解析由 `checkin_protocol.py` 统一归一化：新增脚本直接输出 `__CHECKIN__ {json}` 机器可读行，WorkBuddy / Trae / Qoder 等旧脚本保留原输出格式以兼容上游项目，由协议层兜底解析。
* 豆包 Cookie **只在内存中拼接请求头，不写入本项目任何文件**；`.doubao_done` 只记录日期字符串，`0600`。
* 国际区 renewal 成功得到的新 token 会落在 `~/.auto-checkin/.minimax_token.json`（`0600` 原子写入，7 天软过期），**绝不回写客户端 `~/.minimax/auth/…/auth.json`**；CN 区默认不续期，不会产生该缓存。缓存属于明文凭据，存在时请用 `uninstall.sh --purge` 一并删除。
* 请求仅指向官方域名：`copilot.tencent.com`、`api.trae.cn`、`api.trae.com.cn`、`openapi.qoder.com.cn`、`agent.minimaxi.com` / `agent.minimax.io`（MiniMax）、`www.doubao.com`（豆包）。企业微信 / PushPlus 推送 token 从环境变量读取，默认关闭，无硬编码回传地址。

---

## 📌 版本与校验（维护者建议）

发布时请打 tag 并附 SHA-256，用户安装前可校验，避免直接跟随 `main`（**当前仓库尚未打 tag**，在此之前请先固定到已知 commit SHA）：

```bash
git checkout <tag>            # 换成实际发布的 tag，例如未来的 v1.2.0
shasum -a 256 install.sh scripts/*.py
```

本项目**不提供也不建议启用自动更新**：读的是私有协议，客户端更新随时可能导致脚本失效；固定版本 + 人工升级更安全。五个平台中豆包的活动码、MiniMax 的签名常量与登录态路径最易变化，升级前建议先跑两个 `--dry-run`。

---

## 🤝 致谢与开源参考

感谢开源社区先驱的逆向分析与脚本实践，本项目在开发过程中借鉴了以下优秀的开源成果：

早期三个平台（WorkBuddy / Trae / Qoder）：

* [88lin / workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin)
* [L0NE-6 / Trae-AutoCheckin](https://github.com/L0NE-6/Trae-AutoCheckin)
* [L0NE-6 / WorkBuddy-Daily](https://github.com/L0NE-6/WorkBuddy-Daily)

MiniMax Code 与豆包（2026-11 新增）：

* [MiniMax-AI / minimax-code](https://github.com/MiniMax-AI/minimax-code) — **官方** TUI 的 `/checkin` 实现（`http-gateway.ts` / `public-gateway.ts` / `daily-signin.ts`），端点、签名头与 7 日面板结构以此为准
* [hiclaw168-163 / auto-signin-kit](https://github.com/hiclaw168-163/auto-signin-kit) — 豆包签到接口逆向（NOTE-04）与裸请求风控结论
* [tututashu / doubao-auto-checkin](https://github.com/tututashu/doubao-auto-checkin)（MIT）— macOS 客户端 Cookie 解密链路与幂等前置检查
* [welldo / QinglongMy](https://github.com/welldo/QinglongMy) — `POST /v1/api/user/renewal` 与滚动缓存思路（仅适用于国际区 JWT 体系；本项目 2026-11-13 起 CN 区默认关闭该端点，见续期章节）
* [VICqiufeeng / dsh-minimax-connect](https://github.com/VICqiufeeng/dsh-minimax-connect) — CN 区 `account.minimax.cn/oauth2/token` 的 `refresh_token` grant、单次轮换与 `generation` 规则实测记录，用于查清本次 401 根因（本项目**未**接管该刷新）
* [BorisSun0424-boop / zaoba](https://github.com/BorisSun0424-boop/zaoba)（MIT）— 多平台 launchd 调度设计参考

> 本项目未复制上述仓库代码，仅实现其公开的协议契约；签名常量属于 wire-protocol 值，不是凭据。

---

## 📄 开源许可证

本项目基于 [MIT 许可证](LICENSE) 开源。仅供个人学习与自动化探索使用，请遵守各平台的服务条款。
