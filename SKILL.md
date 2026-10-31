---
name: mac-ai-auto-checkin
description: macOS 专用的 AI 办公与编程助手每日自动签到与积分领取 Skill。支持 WorkBuddy（每日签到+成长中心全任务）、Trae CN（每日签到+额度查询+防9074限流）、Qoder CN（每日 100 Credits）。基于底层 API 协议流与本地桌面凭据自动提取，零外部依赖，通过 macOS launchd 实现免开软件界面、锁屏/合盖唤醒即补跑的全自动静默签到。
---

# 🍎 macOS AI 助手每日自动签到 Skill (`mac-ai-auto-checkin`)

专为 **macOS** 平台设计的 AI 办公与编程助手自动化签到方案。通过无头 API 协议流直接与服务端通信，自动完成每日登录打卡、签到积分领取与额度刷新，无需每日手动打开客户端逐一点选。

---

## 一、 支持的应用与奖励一览

| 应用名称 | 客户端标识 | 每日奖励与覆盖能力 | 刷新时间 (UTC+8) |
| :--- | :--- | :--- | :--- |
| **WorkBuddy** (腾讯) | `/Applications/WorkBuddy.app` | • 每日签到（+100 积分，连续签到累计）<br>• Buddy 旅行礼物领取<br>• 自动开 Buddy 盲盒<br>• 自动领取每日成长中心全部活动任务 | 00:00 |
| **Trae CN** (字节跳动) | `/Applications/Trae CN.app` | • 每日签到（+100 积分 / Tokens）<br>• 实时可用额度回查<br>• 设备指纹自动对齐（内置抗 9074 限流风控保护） | 00:00 |
| **Qoder CN** | `/Applications/Qoder CN.app` | • 每日 100 通用 Credits 自动领取<br>• 适配平台活动 Campaign API 幂等申领 | 10:00 |

---

## 二、 系统与环境要求 (Environment Requirements)

1. **操作系统**：
   * macOS 11.0 (Big Sur) 及以上（包括 Monterey, Ventura, Sonoma, Sequoia 等后续版本）。
   * 架构支持：**Apple Silicon (M1/M2/M3/M4 系列)** 及 **Intel (x86_64)** 均原生完美支持。
2. **Python 运行环境**：
   * **Python 3.8+**。
   * **零第三方依赖**：纯 Python 标准库编写（内置离线纯 Python AES 解密与 macOS 原生加密调用），**无需** `pip install` 安装任何外部包（如 cryptography/requests 等）。
   * 可直接使用系统自带的 `/usr/bin/python3`，或 Homebrew 安装的 Python (`/opt/homebrew/bin/python3`)。
3. **后台调度系统**：
   * 使用 macOS 原生系统级服务管理框架 **`launchd`**（免去安装青龙面板、Docker 或配置第三方守护程序的繁琐）。

---

## 三、 客户端要求 (Client Requirements)

自动化脚本通过读取本地客户端的合法运行时与安全凭据实现无感知登录，因此要求目标客户端已在当前 Mac 上安装：

1. **安装路径**：
   * 默认安装在 macOS 标准应用程序目录 `/Applications/`：
     - `/Applications/WorkBuddy.app`
     - `/Applications/Trae CN.app`
     - `/Applications/Qoder CN.app`
2. **应用架构**：
   * 目标应用均基于 Chromium / Electron / VS Code 架构构建，脚本通过调用 Electron 本地安全存储及解析持久化配置文件来完成离线鉴权。

---

## 四、 登录状态要求 (Login Status Requirements)

为确保自动化脚本能够提取到有效的认证凭证，请遵循以下前置要求：

1. **至少在客户端完成一次登录**：
   * 首次安装客户端后，请先启动并正常登录你的账号（微信扫码、手机号验证码或 OAuth 登录）。
   * 确认客户端内能正常看到你的个人资料与积分页面，即可退出客户端。
2. **凭据提取机制与安全性**：
   * **WorkBuddy**：凭据由客户端写入本地安全存储及 `~/.workbuddy/`，脚本通过调用桌面端自带的无头 Node 运行时安全读取，不会将明文 Token 泄漏至磁盘。
   * **Trae CN**：客户端将登录态保存在 `~/Library/Application Support/Trae CN/User/globalStorage/storage.json`，脚本通过内建的标准库算法离线解密 Token 与已注册设备号，免手动抓包。
   * **Qoder CN**：登录态存储于 `~/Library/Application Support/com.qodercn.app.stable/auth.v1.dat`，并由 macOS 钥匙串保护。
3. **凭据失效与更新**：
   * 如果数月未打开客户端导致 Token 彻底过期被服务端注销，只需重新启动一次客户端完成登录，脚本即刻自动同步最新凭证。

---

## 五、 macOS 钥匙串初次授权指南 (针对 Qoder CN)

macOS 系统对钥匙串（Keychain Access）有严格的应用沙盒保护机制：
* 当外部脚本（终端 Python 进程）首次读取 Qoder 客户端存入钥匙串的加密钥匙时，macOS 会在屏幕中央弹出系统原生授权对话框：
  > *“security 想要访问钥匙串中的「Qoder CN App Safe Storage」。请输入您的登录密码以允许此操作。”*
* **关键操作**：
  在终端中手动执行一次：
  ```bash
  python3 ~/.auto-checkin/qoder_signin.py auto
  ```
  在弹出的系统对话框中输入 **Mac 开机密码**，并**务必点击「始终允许」(Always Allow)**。
* **效果**：系统将永久为该任务放行，后续不论是定时任务还是开机静默运行，均不会再次弹窗阻断。

---

## 六、 锁屏、熄屏与睡眠唤醒机制 (Sleep & Wake Behavior)

很多人担心合盖后无法签到，本方案针对 macOS 的电源管理特性进行了深度优化：

1. **锁屏 / 仅屏幕熄灭（系统未深度休眠）**：
   * 脚本完全正常运行。无头 API 请求不需要图形界面与键鼠介入，网络请求在锁屏下照常执行。
2. **盒盖 / 深度休眠（System Sleep）与唤醒补跑**：
   * 深度休眠期间 Mac 会挂起 CPU 并断开 Wi-Fi 以省电。
   * **`launchd` 唤醒补偿机制**：一旦你在任意时间掀开屏幕唤醒 Mac，`launchd` 会自动侦测到休眠期间错过的定时任务，并在连上 Wi-Fi 的**数秒内自动立即补跑**！
3. **严格的幂等防重保障**：
   * 排程设置了每天 **10:05**、**15:05**、**20:05** 三波次轮询。
   * 脚本具备状态记忆与服务端幂等回查，已签到的应用会在 0.2 秒内静默跳过，绝不会重复发送无效请求或触发风控。

---

## 七、 快速安装与部署

### 1. 一键安装
在终端克隆本项目并执行安装脚本：
```bash
git clone https://github.com/RAyymask/mac-ai-auto-checkin.git
cd mac-ai-auto-checkin
bash install.sh
```

### 2. 常用操作命令
* **手动一键签到全部**：
  ```bash
  ~/.auto-checkin/checkin
  ```
* **实时查看运行日志**：
  ```bash
  tail -f ~/.auto-checkin/checkin.log
  ```
* **查看 launchd 后台服务日志**：
  ```bash
  tail -f ~/.auto-checkin/launchd.out.log
  ```
* **一键卸载清理**：
  ```bash
  bash uninstall.sh
  ```

---

## 八、 自动化通知效果

签到完成后，脚本会通过 macOS 原生通知中心向你推送精美的汇总横幅：

```text
┌──────────────────────────────────────────────┐
│ 每日签到助手                          刚刚  │
│ AI 助手积分领取完毕                          │
│ ✅ WorkBuddy: 今日已签 (+100积分)，连签 4 天 │
│ ✅ Trae: 今日已完成 (+100积分)，当前额度 4600│
│ ✅ Qoder: 成功领取 100 Credits               │
└──────────────────────────────────────────────┘
```
