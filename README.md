# 🍎 mac-ai-auto-checkin

<p align="center">
  <strong>专为 macOS 打造的 AI 办公与编程助手每日自动一键签到 & 积分领取套件</strong><br>
  涵盖 <strong>WorkBuddy</strong> (腾讯) · <strong>Trae CN</strong> (字节跳动) · <strong>Qoder CN</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-macOS%2011.0%2B-black?logo=apple&style=flat-square" alt="macOS">
  <img src="https://img.shields.io/badge/Arch-Apple%20Silicon%20%7C%20Intel-blue?style=flat-square" alt="Architecture">
  <img src="https://img.shields.io/badge/Python-3.8%2B%20(Zero--Dep)-3776AB?logo=python&logoColor=white&style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/Scheduler-macOS%20launchd-007AFF?style=flat-square" alt="launchd">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

---

## 💡 为什么需要这个项目？

很多开发者每天都会使用 **WorkBuddy**、**Trae**、**Qoder** 等 AI 编程助手。为了维持每天的高速并发请求或获得更多使用额度，我们需要每天打开客户端挨个点击签到、领积分或开盲盒。

但这些客户端**没有官方网页版签到入口**，传统方式要么必须人肉每天打开点一遍，要么依赖笨重的 UI 屏幕点击脚本（需要亮屏、解锁，且容易点偏）。

**本项目直接解构客户端的鉴权与签到协议**：
* ⚡ **纯静默 API 协议流**：毫秒级完成，不需要启动客户端界面，电脑完全不闪烁。
* 🪶 **零外部依赖**：纯 Python 标准库编写，无需 `pip install` 安装任何第三方包。
* 🔒 **隐私绝对安全**：仅在本地读取你机器上已登录的 Session，不上传任何凭据，不设内置密钥。
* ⏰ **唤醒自动补签**：深度结合 macOS 原生 `launchd`，**熄屏锁屏照常跑，即便合盖休眠，只要掀开屏幕唤醒系统，数秒内自动补跑完成，绝不漏签！**

---

## 🎁 支持平台与每日权益

| 助手客户端 | 路径与标识 | 自动化功能范围 | 刷新时间 (UTC+8) |
| :--- | :--- | :--- | :--- |
| **WorkBuddy**<br>(腾讯生态) | `/Applications/WorkBuddy.app` | • 每日签到（+100 积分，连续签到累计）<br>• 自动开 Buddy 盲盒（+积分/能量）<br>• 自动领取 Buddy 旅行礼物<br>• 自动接取成长中心全量活动任务 | 00:00 |
| **Trae CN**<br>(字节跳动) | `/Applications/Trae CN.app` | • 每日签到（+100 积分/额度）<br>• 实时可用额度与消耗回查<br>• 设备指纹自动对齐（抗 9074 限流保护机制） | 00:00 |
| **Qoder CN** | `/Applications/Qoder CN.app` | • 每日通用 100 Credits 自动 Claim<br>• 本地钥匙串凭证解密与 Campaign 状态回查 | 10:00 |

---

## 📋 环境与前置要求

1. **操作系统**：macOS 11.0 (Big Sur) 或更高版本（兼容 macOS Sequoia 及后续系统，支持 M1/M2/M3/M4 系列芯片及 Intel 架构）。
2. **Python**：macOS 系统自带的 `/usr/bin/python3` 或 Homebrew Python (3.8+) 即可，**无需安装任何 pip 依赖**。
3. **客户端状态**：
   * 对应 App 已安装在 `/Applications/` 目录下；
   * 电脑上**至少打开并登录过一次**对应的客户端账号（确保本地已生成合法认证会话）。

---

## 🚀 快速开始

### 1. 克隆并一键安装

打开 macOS「终端 (Terminal)」，依次执行：

```bash
# 1. 克隆仓库
git clone https://github.com/RAyymask/mac-ai-auto-checkin.git
cd mac-ai-auto-checkin

# 2. 运行一键安装脚本
bash install.sh
```

`install.sh` 将自动完成以下工作：
1. 检查 Python 3 环境；
2. 部署核心脚本至 `~/.auto-checkin/`；
3. 生成并加载 macOS 系统服务配置 `~/Library/LaunchAgents/com.user.ai-daily-checkin.plist`；
4. 立即触发一次全自动化自检与试运行。

---

### 2. Qoder 钥匙串初次授权（只需点一次）

由于 macOS 系统钥匙串的安全保护，当外部 Python 进程初次访问 Qoder 桌面端的存储密钥时，macOS 会在屏幕中央弹窗请求授权：

```bash
# 在终端中运行一次以触发授权弹窗
python3 ~/.auto-checkin/qoder_signin.py auto
```

* **屏幕弹出系统弹窗**（*“security 想要访问钥匙串中的 Qoder CN App Safe Storage”*）；
* 请输入你的 **Mac 开机密码**，并**务必点击「始终允许」(Always Allow)**；
* 点击后即刻完成领取，今后后台静默运行将**永久自动放行，不再弹窗**。

---

## 🛠️ 常用管理指令

* **手动立即执行一次全量签到**：
  ```bash
  ~/.auto-checkin/checkin
  ```
* **查看每日签到结果与明细日志**：
  ```bash
  tail -n 25 ~/.auto-checkin/checkin.log
  ```
* **实时追踪日志流**：
  ```bash
  tail -f ~/.auto-checkin/checkin.log
  ```
* **一键卸载（清理 launchd 服务及相关文件）**：
  ```bash
  bash uninstall.sh
  ```

---

## 💤 熄屏、锁屏与合盖唤醒机制

很多人担心：“我的 MacBook 经常合盖装在包里，会不会错过签到？”

* **锁屏 / 仅屏幕熄灭**：Mac 并没有真正休眠，网络连接正常，脚本在设定的时间点（10:05 / 15:05 / 20:05）会在后台毫秒级静默完成签到。
* **合盖 / 深度休眠**：休眠期间 CPU 暂停以省电。但借助 macOS `launchd` 的排程补偿机制（Catch-Up），**只要你在一天中的任意时刻掀开屏幕，系统检测到错过定时后，会在连上 Wi-Fi 的数秒内自动补跑！**
* **严格幂等防风控**：脚本内置服务端回查，如果今日已经签过到，0.2 秒内直接跳过，不会重复请求，也不会触发官方风控机制。

---

## 🔔 桌面原生通知

每次签到完成后，脚本会通过 macOS 通知中心弹出汇总通知：

```text
┌──────────────────────────────────────────────┐
│ 每日签到助手                          刚刚   │
│ AI 助手积分领取完毕                          │
│ ✅ WorkBuddy: 今日已签 (+100积分)，连签 4 天  │
│ ✅ Trae: 今日已完成 (+100积分)，当前额度 4600 │
│ ✅ Qoder: 成功领取 100 Credits                │
└──────────────────────────────────────────────┘
```

---

## 🤝 致谢与开源参考

感谢开源社区先驱的逆向分析与脚本实践，本项目在开发过程中借鉴了以下优秀的开源成果：
* [88lin / workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin)
* [L0NE-6 / Trae-AutoCheckin](https://github.com/L0NE-6/Trae-AutoCheckin)
* [L0NE-6 / WorkBuddy-Daily](https://github.com/L0NE-6/WorkBuddy-Daily)

---

## 📄 开源许可证

本项目基于 [MIT 许可证](LICENSE) 开源。仅供个人学习与自动化探索使用，请遵守各平台的服务条款。
