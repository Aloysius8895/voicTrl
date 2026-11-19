# 02 · 设备控制、唤醒、文件传输、Windows 自动化、编码代理与开发/部署工具 调研

- 调研日期：2026-11-18（Demo 日期 2026-11-28，Physical AI Hackathon Malaysia 2026）
- 方法：只以一手来源为准（微软 / Anthropic / Espressif / AWS / Cloudflare / ngrok 官方文档，GitHub 仓库 README 与源码，PyPI 与 ESP 组件注册表）。每条结论后给出来源 URL。GitHub 页面若不显示发布年份，原样注明“年份未显示”。
- 本机只读核对：`claude --version` = `2.1.322 (Claude Code)`；`code --version` = `1.146.0`；本机系统 Windows 11 Home Single Language。

---

## 0. 结论速览

### 0.1 对本项目最有用的 8 个

| # | 名称 | 一句话理由 |
|---|---|---|
| 1 | **Claude Code 无头模式 `claude -p`** + `claude setup-token` | B 上用 `claude -p "<prompt>" --output-format stream-json --verbose --permission-mode acceptEdits --max-budget-usd 2` 生成网页，逐行 JSON 事件可转发到云端；`setup-token` 生成 1 年期 OAuth token，可做无人值守认证。https://code.claude.com/docs/en/headless ，https://code.claude.com/docs/en/authentication |
| 2 | **Espressif `esp_tinyusb` ≥ 2.1.0 的 `tinyusb_remote_wakeup()`** | 方案 2（ESP32-S3 插在笔记本上当 USB HID，发 USB remote wakeup）的官方 API，已进入正式版本，当前最新版是 3.0.1。https://components.espressif.com/components/espressif/esp_tinyusb |
| 3 | **nonoo/esp-remote-wakeup** | 现成参考实现：ESP32-S3 + ESP-IDF + TinyUSB，HTTP `GET /wakeup?pass=…` 触发 `tud_remote_wakeup()`，MIT 许可。把 HTTP 触发换成云端 WSS 指令即可用。https://github.com/nonoo/esp-remote-wakeup |
| 4 | **`powercfg`**（`/a`、`/devicequery wake_armed`、`/lastwake`、`/requests`、`/spr`）+ 微软电源设置文档 | 在 A/B 实机上 1 小时内判断 Wi-Fi WoL 是否可用的唯一可靠办法：看是不是 Modern Standby、哪些设备允许唤醒、上次是谁唤醒的、睡眠期间是否联网。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options |
| 5 | **FastAPI WebSocket + Python `websockets` 客户端**（`async for ws in connect(...)` 自动重连） | 薄 device agent 与云协调器的骨架：出站 WSS，握手头带 token，断线后指数退避重连。睡眠/唤醒后必然掉线，所以自动重连是必需的。https://fastapi.tiangolo.com/advanced/websockets/ ，https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html |
| 6 | **Caddy（自动 HTTPS，reverse_proxy 透传 WebSocket）+ AWS Lightsail（有 Malaysia 区域）** | 一台每月 5–12 美元的 Lightsail 加两行 Caddyfile，就有固定的公网 HTTPS/WSS；没有域名时可以用 `<IP>.nip.io` 主机名申请 Let's Encrypt 证书。https://caddyserver.com/docs/automatic-https ，https://aws.amazon.com/lightsail/pricing/ ，https://nip.io/ |
| 7 | **VS Code CLI（`code -n`、`-g file:line`）+ Claude Code 扩展 URI `vscode://anthropic.claude-code/open?prompt=…&session=…`** | 在用户指定的电脑上打开结果，不需要 GUI 自动化：`code` 打开项目，`Start-Process` 打开浏览器或 URI；扩展 URI 能预填 prompt，也能按 session ID 恢复会话。https://code.visualstudio.com/docs/configure/command-line ，https://code.claude.com/docs/en/vs-code |
| 8 | **Windows 任务计划程序“登录时”启动**（`schtasks /create /sc onlogon /it …`） | agent 必须运行在用户交互会话里才能弹出 VS Code 和浏览器；用 NSSM 装成服务会跑在不可交互的 Session 0。https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create ，https://learn.microsoft.com/en-us/previous-versions/bb756986(v=msdn.10) |

### 0.2 建议：自写“薄”device agent；MeshCentral / OpenClaw / UFO 只作参考

**推荐自写一个几百行的 Python device agent**：出站 WSS 连到 FastAPI 协调器，只实现少量确定性指令，例如 `wake_peer`、`fetch_artifact`、`run_claude`、`upload_result`、`open_result`、`ack`。原因如下：

- **MeshCentral**（Apache-2.0，活跃，Windows agent 成熟）已经实现了我们要的“让同一设备组里在线的 agent 代发 WoL”。服务器的 `wakedevices` 处理会向用户有唤醒权限的设备组内所有已连接 agent 发送 `{action:'wakeonlan', macs}`（源码 https://github.com/Ylianst/MeshCentral/blob/master/meshuser.js ）。`meshctrl` 也有 `RunCommand`、`Upload`、`Download`、`DevicePower --wake`（https://github.com/Ylianst/MeshCentral/blob/master/meshctrl.js ）。但它是一整套 Node.js 服务器（`package.json` 要求 node ≥ 22.21.1）加独立 agent 二进制，要接入我们自己的 FastAPI 协调器和 ESP32 还得再写一层桥接，“语音 → 云 → 设备”的演示主线也会被一个通用 RMM 面板冲淡。**结论：作为设计参考；万一自写 agent 来不及，可作为应急 Plan C 直接演示 WoL、远程执行和文件传输。**
- **OpenClaw**（MIT，非常活跃）有 Gateway + nodes 架构（WebSocket，`role: "node"`，Windows 可作 node host）。但 `openclaw nodes invoke` 明确屏蔽了 `system.run`，执行 shell 必须走 agent 的 `exec` 工具，也就是 LLM 在环（https://docs.openclaw.ai/cli/nodes ）。Gateway 绑定在 loopback 时，远程 node 要用 SSH 隧道（https://docs.openclaw.ai/nodes/node-host ）。这不适合确定性的演示流水线。**结论：参考。**
- **microsoft/UFO³ Galaxy**（MIT）是由 LLM 规划的多设备 DAG 编排（Windows/Linux/Android），每台设备要跑 server + client，Galaxy 侧需要配置 Azure OpenAI 或 OpenAI 密钥，文档示例都是 localhost（https://microsoft.github.io/UFO/getting_started/quick_start_galaxy/ ）。**结论：概念上和本项目最接近，但依赖重、规划结果不确定，只作参考。**
- **Tactical RMM** 的许可证声明自己不是开源许可证，服务器需要 Debian/Ubuntu、≥4GB 内存和 3 个子域名。**Open Interpreter 01** 最近一次提交是 2024-11-01。**HASS.Agent** 需要 Home Assistant + MQTT，而且 HA 要部署在局域网内。**三者都不用。**（来源见 §1.3）

### 0.3 对唤醒方案的直接影响（先读这 6 条）

1. **先在 A/B 上运行 `powercfg /a`，确认是 Modern Standby（S0 低功耗空闲）还是 S3。** 按微软文档，Modern Standby 下桌面应用在 DAM 阶段会被暂停，此后在待机的任何阶段都不能运行；Session 0 服务被限流到每 30 秒最多运行 1 秒；“网络安静模式”下第三方服务看到的网络是断开的。所以我们的 Python agent 在睡眠期间**一定会掉线**，唤醒后必须自动重连。（§2.1-B）
2. **Modern Standby 下的 Wi-Fi WoL 是一条“弱”路径。** 微软唤醒源表把 Wi-Fi radio 列为“能唤醒 SoC 但不能点亮屏幕”；远程桌面和文件共享的唤醒只在以太网下可用；NDIS 关键字 `*ModernStandbyWoLMagicPacket`（S0ix 下收到魔术包唤醒）**默认是 Disabled**；Surface 官方 WoL 也要求接 AC 电源和以太网。即使 Wi-Fi WoL 唤醒了 SoC，被 DAM 暂停的 agent 会不会恢复运行，文档没有写，**必须实机测试**。（§2.1-C）
3. **方案 2 的 USB HID 唤醒在微软表中属于“用户输入”，会点亮屏幕。** 但文档同时写明“可能需要多次按键才产生 resume 事件”“为省电，键盘唤醒可能被禁用”，而且 24H2 起**合盖时会启用输入抑制，屏幕不亮**。所以演示时笔记本要开盖（或接外接显示器），并接 AC。（§2.1-D）
4. **ESP32 侧用 ESP-IDF + esp_tinyusb ≥ 2.1.0**，不要用 Arduino-ESP32 自带的 USB 栈：arduino-esp32 #10831 报告 ESP32-S3 从不进入 USB suspend，因此无法唤醒 PC。该 issue 于 2026-10-14 以“针对旧版本”为由关闭，没有给出修复版本。（§2.2）
5. **唤醒后保持清醒。** 接 AC 时，agent 用 `SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED)` 持有电源请求，可以无限期阻止进入睡眠；用电池时最多只能阻挡 5 分钟。这个调用不能阻止用户合盖或按电源键。（§2.1-F）
6. **唤醒后需要登录。** 所有 Windows 桌面版默认开启“唤醒时需要密码”（`CONSOLELOCK`）。组策略对应的 Policy CSP 适用版本列表里没有 Home 版，家庭版只能用 powercfg 的隐藏设置或系统设置界面处理。（§2.1-G）

---

## 1. 分类表格

### 1.1 唤醒 · ESP32 USB HID remote wakeup（方案 2）

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| nonoo/esp-remote-wakeup | https://github.com/nonoo/esp-remote-wakeup | ESP32（作者用 ESP32-S3-DevKitC）模拟 USB 键盘。`GET /wakeup?pass=<密码>`（默认密码 `wakeup`，主机名 `esp-wakeup-keypress.localdomain`）或按板上按键时调用 `tud_remote_wakeup()`。配置描述符带 `TUSB_DESC_CONFIG_ATT_REMOTE_WAKEUP`，键盘报告代码被注释掉，只发 remote wakeup 信号；未 mounted 时不发 | MIT；19 次提交，最近一次 2026-09-18（新增按小时定时重启）；`dependencies.lock` 锁定 esp_tinyusb 1.3.1、tinyusb 0.19.0~1、idf 5.1.0；作者的排障说明基于 Linux（systemd 睡眠钩子为 USB 设备 `303a:4004` 开启唤醒），没有提到 Windows | fork 后把 HTTP 触发改为订阅云端 WSS `wake` 指令；或保留 HTTP，由同一 LAN 内的另一台 ESP32 调用。建议升级到 esp_tinyusb ≥2.1.0，改用 `tinyusb_remote_wakeup()` 并检查返回码 | **参考 / fork** | README：https://github.com/nonoo/esp-remote-wakeup ；源码：https://raw.githubusercontent.com/nonoo/esp-remote-wakeup/master/main/usb.c ；依赖：https://raw.githubusercontent.com/nonoo/esp-remote-wakeup/master/dependencies.lock ；提交记录：https://api.github.com/repos/nonoo/esp-remote-wakeup/commits |
| esp_tinyusb（espressif/esp-usb） | https://components.espressif.com/components/espressif/esp_tinyusb | Espressif 的 TinyUSB 设备栈组件：HID 等设备类，`TINYUSB_EVENT_SUSPENDED`/`RESUMED` 事件，`esp_err_t tinyusb_remote_wakeup(void)` | 许可证本次未核实；最新 3.0.1；remote wakeup API 来自 PR #387（2026-02-02 合并），随 v2.1.0 发布（release PR #394 于 2026-02-05 合并）；3.0.0 起不再支持 ESP-IDF < 5.3；支持 esp32s2/s3/p4/h4/s31 | ESP32-S3 唤醒棒固件的 USB 部分：在 SUSPENDED 事件里记录 `remote_wakeup`（主机是否允许远程唤醒），收到云端指令后调用 `tinyusb_remote_wakeup()` | **直接用** | https://raw.githubusercontent.com/espressif/esp-usb/master/device/esp_tinyusb/include/tinyusb.h ；https://raw.githubusercontent.com/espressif/esp-usb/master/device/esp_tinyusb/CHANGELOG.md ；https://github.com/espressif/esp-usb/pull/387 ；https://github.com/espressif/esp-usb/pull/394 ；https://components.espressif.com/components/espressif/esp_tinyusb/versions/2.1.0 |
| esp-usb 设备栈文档 | https://docs.espressif.com/projects/esp-usb/en/latest/esp32s3/usb_device.html | 官方说明：栈始终实现 `tud_suspend_cb()`/`tud_resume_cb()`，应用自行定义会导致链接错误；设备可调用 `tinyusb_remote_wakeup()` 向主机发 resume，但只能在 suspended 且主机已允许远程唤醒时调用；HID 示例 `tusb_hid` 实现键盘和鼠标 | 官方文档 | 开发时照文档写事件回调 | **直接用** | 同左 |
| TinyUSB `tud_remote_wakeup()` | https://github.com/hathach/tinyusb | 底层实现：`TU_VERIFY(_usbd_dev.suspended && _usbd_dev.remote_wakeup_en)`；`remote_wakeup_en` 由主机的 SET_FEATURE(DEVICE_REMOTE_WAKEUP) 置 1，CLEAR_FEATURE 清 0 | MIT（源码文件头注明） | 排查“为什么唤不醒”：只有同时满足“已挂起”和“主机已允许”才会发信号 | 了解即可（经 esp_tinyusb 间接使用） | https://raw.githubusercontent.com/hathach/tinyusb/master/src/device/usbd.c ；https://raw.githubusercontent.com/hathach/tinyusb/master/src/device/usbd.h |
| Arduino-ESP32 自带 USBHIDKeyboard | https://github.com/espressif/arduino-esp32/issues/10831 | Arduino 核心自带的 USB HID | issue：ESP32-S3 + core 3.1，PC 睡眠后设备从不进入 USB suspend，因此无法唤醒；S2 + core 3.1.1 也有人复现；2026-10-14 以“针对旧版本”关闭，没有说明修复版本 | — | **不用** | 同左 |
| Adafruit TinyUSB Library（Arduino） | https://github.com/espressif/arduino-esp32/issues/10831 | Arduino 下的替代 USB 栈 | issue 中有用户报告 core 3.1.1 + Adafruit TinyUSB 3.4.3、core 3.2.0 + 3.7.0 可以唤醒（用户报告，不是官方结论） | 只有在团队只会 Arduino 时作为退路 | 备选（证据弱） | 同左 |

### 1.2 唤醒 · WoL 发送端、WoL 应用与中继（方案 1）

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| a7md0/WakeOnLan | https://github.com/a7md0/WakeOnLan | ESP8266/ESP32 的 Arduino 魔术包生成与发送库 | MIT；224 stars；最近推送 2025-04-17；未归档 | 唤醒棒用 Arduino 写时，一行代码发 WoL | 可用（也可以在 ESP-IDF 里自己用 UDP 发） | https://api.github.com/repos/a7md0/WakeOnLan |
| ESP-IDF 自己发 UDP 广播 | — | 魔术包内容是目标网卡以太网地址连续重复 16 次（微软定义） | 本次没有在 ESP 组件注册表找到官方 WoL 组件（只做了搜索，没有穷举） | 在 ESP-IDF 中用 lwIP socket 发到 `255.255.255.255:9` 或子网广播地址 | 自写（很简单） | 魔术包定义：https://learn.microsoft.com/en-us/windows-hardware/drivers/network/standardized-inf-keywords-for-power-management |
| seriousm4x/UpSnap | https://github.com/seriousm4x/UpSnap | WoL Web 面板（Go + PocketBase + SvelteKit）：一键唤醒、cron 定时、端口 ping、nmap 扫描、自定义关机命令、按用户分配设备权限 | MIT；6.4k stars；最新 5.7.3（2026-11-06），发布资产含 `windows_amd64`/`windows_arm64` 二进制；Docker 示例用 `--network=host` | 赛前在旅行路由器的 LAN 上，用现成工具快速验证“A/B 能否被 Wi-Fi WoL 唤醒”，排除我们自己代码的问题 | **测试工具 / 参考** | README：https://raw.githubusercontent.com/seriousm4x/UpSnap/master/README.md ；发布：https://api.github.com/repos/seriousm4x/UpSnap/releases/latest |
| kyori19/wol-proxy | https://pkg.go.dev/github.com/kyori19/wol-proxy | “不在家里开端口”的 WoL：公网上跑 server，局域网内跑 client，两者通过 WebSocket 通信，client 不需要暴露到公网 | MIT；v1.0.0（2020-12-24，页面提示不是最新版本） | 与“云协调器 + LAN 内唤醒棒出站连接”同构，可以借鉴协议设计 | 参考 | 同左 |
| seanauff/WOL-proxy | https://github.com/seanauff/WOL-proxy | 订阅 MQTT `WOL-proxy/command`，收到 MAC 地址后发魔术包；在 `/status` 上发布 retained 的在线/离线状态 | MIT；Python（paho-mqtt + wakeonlan）；README：容器必须用 host 网络才能正确发广播 | 如果改用 MQTT，可参考它的主题设计 | 参考 | 同左 |
| Home Assistant Wake on LAN 集成 | https://www.home-assistant.io/integrations/wake_on_lan/ | `wake_on_lan.send_magic_packet`（`mac`，`broadcast_port` 示例为 9）；按钮无状态，无法确认目标是否真的醒了 | HA 官方集成 | 不引入 HA | 不用 | 同左 |
| MeshCentral 的“由 agent 代发 WoL” | https://github.com/Ylianst/MeshCentral/blob/master/meshuser.js | 服务器先自己尝试发 WoL（源码注释说 WAN-only 时无效），再让用户有唤醒权限的设备组内所有已认证在线 agent 代发；设备通过 MQTT 连接时还会发布 `powerAction: wake` | 见 §1.3 | 设计参考：由 A 的 agent（或 LAN 内任一在线设备）代发 WoL 唤醒 B | 参考 | 源码（`wakedevices` 分支） |

### 1.3 远程设备代理框架（能否代替自写 agent）

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| MeshCentral | https://github.com/Ylianst/MeshCentral | 自托管的 Web 远程管理：远程桌面、终端、文件管理；每台电脑装 agent。`meshctrl`（Node.js）支持 `RunCommand --id … --run "…" [--powershell] [--reply]`、`Upload`、`Download`、`DevicePower --wake`，以及 `--loginkey`/`--loginkeyfile`/`--url wss://…` | Apache-2.0；7.7k stars；最近推送 2026-11-18；`package.json` 版本 1.3.1（发布页显示 10 月 23 日，年份未显示），要求 node ≥ 22.21.1；有 Windows/Linux/macOS 安装说明 | 不做主方案。应急 Plan C：云上装 MeshCentral，两台笔记本装 agent，用 `meshctrl` 演示唤醒、执行和传文件。借鉴“同组在线 agent 代发 WoL”的设计 | **参考（应急可直接用）** | https://raw.githubusercontent.com/Ylianst/MeshCentral/master/readme.md ；https://raw.githubusercontent.com/Ylianst/MeshCentral/master/meshctrl.js ；https://docs.meshcentral.com/meshctrl/ ；https://api.github.com/repos/Ylianst/MeshCentral ；https://github.com/Ylianst/MeshCentral/releases |
| Tactical RMM | https://github.com/amidaware/tacticalrmm | Django + Vue + Go agent 的 RMM，集成 MeshCentral；远程 shell、文件浏览（上传/下载）、脚本执行等；README 未提 WoL | “Tactical RMM License 1.0”，原文写明“不是开源软件许可证”，商用需书面批准；最新 v1.6.1（10 月 27 日，年份未显示）；agent 支持 Windows 7/8.1/10/11 等；服务器需全新 Debian 13 或 Ubuntu 26.04、≥4GB 内存、3 个子域名 | — | **不用** | https://docs.tacticalrmm.com/license/ ；https://docs.tacticalrmm.com/install_server/ ；https://github.com/amidaware/tacticalrmm/releases |
| OpenClaw | https://github.com/openclaw/openclaw | 本地 AI 助手。Gateway 是会话、工具、事件的控制面；node 以 `role:"node"` 通过 Gateway WebSocket 连接，暴露命令（headless node host 提供 `system.run`、`system.which` 等）；配对分两步：先批准设备，再批准命令面；`openclaw node install` 在 Windows 上注册为任务计划 | MIT；约 395k stars；最新 v2026.11.5（2026-11-17）；Windows Hub 原生应用可作为 node，不支持 Windows Server | `openclaw nodes invoke` 屏蔽 `system.run`/`system.run.prepare`，shell 执行必须经 agent 的 `exec` 工具（LLM 在环）；Gateway 绑定 loopback 时，远程 node 要走 SSH 隧道；node host 页面没有文件传输命令 | **参考** | https://docs.openclaw.ai/nodes ；https://docs.openclaw.ai/nodes/node-host ；https://docs.openclaw.ai/cli/nodes ；https://docs.openclaw.ai/platforms/windows ；https://github.com/openclaw/openclaw/releases |
| HASS.Agent（社区续作 hass-agent/HASS.Agent） | https://github.com/hass-agent/HASS.Agent | Windows 客户端：通过 MQTT 把命令和传感器接入 Home Assistant；原项目说明中 Satellite Service 可在无人登录时运行 | MIT；.NET 8，只支持 Windows；最新 2.2.1（6 月 7 日，年份未显示）；原仓库 LAB02-Research 最新发布为 2022.14.0 | 需要在 LAN 上部署 HA + MQTT，与“云协调器”架构冲突 | **不用** | https://github.com/hass-agent/HASS.Agent ；https://github.com/hass-agent/HASS.Agent/releases ；https://github.com/LAB02-Research/HASS.Agent |
| Open Interpreter 01 | https://github.com/OpenInterpreter/01 | 语音助手设备的实验项目 | AGPL-3.0；页面没有归档横幅，但最近提交是 2024-11-01；README 自称“实验性、缺乏基本防护” | — | **不用**（实际已停更约 2 年） | https://github.com/OpenInterpreter/01 ；https://github.com/OpenInterpreter/01/commits/main |
| microsoft/UFO（UFO² + UFO³ Galaxy） | https://github.com/microsoft/UFO | UFO²：Windows 桌面 agent（LTS）。Galaxy：ConstellationAgent 把请求拆成任务 DAG，按能力分配给多台设备（Windows/Linux/Android），设备间通过基于 WebSocket 的 AIP 协议通信 | MIT；10.2k stars；最近提交 2026-10-14；README 标注 Galaxy 为 “Active Development” | 每台设备运行 `python -m ufo.server.app --port 5000` 和 `python -m ufo.client.client --ws --ws-server ws://…/ws --platform windows`；`config/galaxy/devices.yaml` 填 `server_url`；Galaxy 的 `agent.yaml` 需要 Azure OpenAI 或 OpenAI 的 API_KEY | **参考**（概念最接近，但依赖重、LLM 规划不确定） | README；https://microsoft.github.io/UFO/galaxy/overview/ ；https://microsoft.github.io/UFO/getting_started/quick_start_galaxy/ ；https://github.com/microsoft/UFO/commits/main |

### 1.4 Windows GUI 自动化 / 打开结果给用户确认

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| VS Code CLI `code` | https://code.visualstudio.com/docs/configure/command-line | `-n`/`--new-window` 新会话窗口；`-r` 复用最近的窗口；`-g file:line[:character]` 打开到指定位置；`-w` 等待文件关闭；`--add` 往当前窗口添加文件夹；URL 形式 `vscode://file/{完整路径}:line:column` | 官方。文档说 Windows 安装应把 `bin` 目录加入 PATH（默认 `AppData\Local\Programs\Microsoft VS Code\bin`）；本机版本 1.146.0 | `open_result` 指令：`code -n <项目目录> -g <项目目录>\index.html` | **直接用** | 同左 |
| Claude Code VS Code 扩展的 URI handler | https://code.claude.com/docs/en/vs-code | `vscode://anthropic.claude-code/open`：`prompt` 参数预填内容（需要 URL 编码，**不会自动提交**）；`session` 参数恢复“VS Code 当前打开文件夹”里的某个会话；VS Code 没运行时会先启动；Windows 下可用 PowerShell `Start-Process "vscode://anthropic.claude-code/open"` | 官方文档 | 在 B 上：headless 运行拿到 `session_id`，用 `code` 打开项目文件夹，再 `Start-Process "vscode://anthropic.claude-code/open?session=<id>"` 展示对话过程（headless 会话能否被识别需实测）。在其他电脑上只能预填 prompt | **直接用（加分项）** | 同左 |
| Claude Code `claude-cli://` 深链 | https://code.claude.com/docs/en/deep-links | `claude-cli://open?cwd=<绝对路径>&q=<URL 编码 prompt>`：在新终端里打开交互式 Claude Code 并预填 prompt（**不自动发送**，`q` 最多 5000 字符）。Windows 用 `Start-Process "<url>"`；需要先在该机的交互式会话里发送过任意内容，handler 才会注册到 `HKCU\Software\Classes\claude-cli`；Windows 依次优先 Windows Terminal、PowerShell、cmd | 官方文档 | 可选：在用户指定的电脑上打开终端会话，方便用户继续提“下一步修改” | 可选 | 同左 |
| 默认浏览器 / URI 打开 | https://code.claude.com/docs/en/deep-links | PowerShell 的 `Start-Process` 会把 URL 交给系统注册的 handler（文档以 `claude-cli://` 为例） | — | `Start-Process "http://…"` 或 `Start-Process "<index.html 路径>"` 打开结果页 | 直接用 | 同左 |
| CursorTouch/Windows-MCP | https://github.com/CursorTouch/Windows-MCP | 基于 UI Automation 的 MCP server，工具有 App、PowerShell、Click、Type、Scroll、Shortcut、Snapshot、Screenshot、Clipboard、FileSystem 等；传输方式有 `stdio`（默认）、`sse`、`streamable-http`（README 推荐生产使用）；远程模式支持 Bearer、IP 白名单、TLS、OAuth 2.0 PKCE | MIT；约 11.9k stars；`pyproject.toml` 版本 0.8.9，**`requires-python >=3.14`**；最近提交 2026-11-18；支持 Windows 10/11；启动命令 `uvx windows-mcp serve` | 加分项：让 B 上的 Claude 通过 MCP 操作 GUI。基础流程不需要 | 可选 / 参考 | README；https://raw.githubusercontent.com/CursorTouch/Windows-MCP/main/pyproject.toml ；https://github.com/CursorTouch/Windows-MCP/commits/main |
| pywinauto | https://github.com/pywinauto/pywinauto | Python 的 Windows GUI 自动化，后端有 `win32`（默认）和 `uia` | BSD-3-Clause；最新稳定版 0.6.9（1 月 6 日，年份未显示），1.0.0b1 是预发布 | 需要确定性点按某个按钮时，比 MCP 更轻量 | 备用 | README；https://github.com/pywinauto/pywinauto/releases |
| UFO²（单机） | https://github.com/microsoft/UFO | LLM 驱动的 Windows 桌面 agent | 见 §1.3 | 对“打开文件给用户看”来说太重 | 不用 | 同左 |

### 1.5 笔记本之间的文件传输

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| **自建：经云协调器上传/下载 artifact** | （自写） | A 用 HTTPS `PUT /artifacts/{id}` 上传 prompt 文件（或直接作为 WSS 小消息发送），云端把 `{artifact_id, sha256}` 推给 B，B 再 `GET` 下载；生成的网页也同样回传给用户指定的电脑 | 依赖已经决定的 FastAPI + HTTPS；客户端用 httpx | 所有设备本来就出站连云，不依赖 LAN 互通，不受路由器 AP 隔离或 Windows“公用网络”配置影响；prompt 文件很小 | **推荐** | 设备之间直连会受 AP 隔离和 Windows“公用网络”影响（LocalSend 排障表）：https://github.com/localsend/localsend |
| croc | https://github.com/schollz/croc | 命令行文件传输，用 PAKE 码做端到端加密；P2P 失败时回退到 relay；`croc relay` 可自托管（默认 TCP 9009–9013，至少要 2 个端口）；`--yes --overwrite` 跳过确认 | MIT；41k stars；最新 v11.6.5（2026-11-07），有 Windows 32/64/ARM64 的 zip；README 给了 `scoop install croc`、`choco install croc`；在 Linux/macOS 上密钥要通过 `CROC_SECRET` 环境变量传入 | 备选：在云主机上跑 `croc relay`，A 发送，B 用 WSS 下发的码接收 | 备选 | README；https://github.com/schollz/croc/releases/expanded_assets/v11.6.5 |
| LocalSend 及其协议 | https://github.com/localsend/localsend ，https://github.com/localsend/protocol | 局域网 REST 协议（`/api/localsend/v2/register`、`prepare-upload`、`upload`、`cancel`、`prepare-download`），默认端口 53317，组播地址 224.0.0.167；可设 PIN；由接收方决定接受、部分接受或拒绝 | Apache-2.0；99.6k stars；最新 v1.18.2（2026-08-21）；Windows 10+；官方 CLI 只通过 Homebrew 提供（macOS/Linux），且只能发送；**仅限 LAN** | 需要路由器关闭 AP 隔离、Windows 网络设为“专用”；GUI 需人工点接受 | **不用**（协议可参考） | README 的 CLI 与排障章节；协议 README |
| Syncthing | https://github.com/syncthing/syncthing | 持续文件同步 | MPL-2.0；90.6k stars；最新 v2.1.7（2026-10-21）；文件监视器默认把变更攒 10 秒后再同步 | 一次性传一个 prompt 文件用不着这么重，还有延迟 | **不用** | README；https://docs.syncthing.net/users/syncing.html ；https://github.com/syncthing/syncthing/releases |

### 1.6 Claude Code 作为 B 的编码代理

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| Claude Code CLI 无头模式 | https://code.claude.com/docs/en/headless | `claude -p` 非交互运行；`--output-format text/json/stream-json`；`--json-schema` 结构化输出；`--permission-mode`、`--allowedTools`、`--tools`、`--max-budget-usd`、`--max-turns` 等（详见 §2.3） | 官方；本机 2.1.322；系统要求 Windows 10 1809+；Windows 上 Git for Windows 是可选的，没装时 Claude 用 PowerShell 工具执行命令 | B 的 agent 用 `subprocess` 启动，在固定的空项目目录里运行，把 stream-json 逐行转发给云端 | **直接用** | headless；https://code.claude.com/docs/en/cli-reference ；https://code.claude.com/docs/en/setup.md |
| `claude setup-token` / `CLAUDE_CODE_OAUTH_TOKEN` | https://code.claude.com/docs/en/authentication | 生成 1 年期 OAuth token，只能发模型请求 | 需要 Pro/Max/Ultra/Team/Enterprise 订阅 | 在 B 上设为用户环境变量，供 agent 无人值守调用（也可以改用 `ANTHROPIC_API_KEY`） | **直接用** | 同左 |
| Claude Agent SDK（Python） | https://github.com/anthropics/claude-agent-sdk-python | `query()`、`ClaudeSDKClient`；用 `@tool` + `create_sdk_mcp_server` 定义进程内自定义工具；hooks 是 Python 函数；`allowed_tools`/`disallowed_tools`/`permission_mode`/`cwd`/`max_turns`；包内自带 Claude Code CLI | MIT（同时受 Anthropic 商业条款约束）；PyPI 0.2.184，Python ≥3.10 | 想在 agent 里做工具审批回调或自定义工具时用；否则 CLI 子进程更简单 | 可选 | README；https://pypi.org/pypi/claude-agent-sdk/json ；https://code.claude.com/docs/en/agent-sdk/overview.md |
| Claude Code Remote Control | https://code.claude.com/docs/en/remote-control | 在 claude.ai/code 或 Claude App 上继续本机会话。本机只发出站 HTTPS，不开入站端口；`claude remote-control`（服务器模式）支持 `--name`、`--spawn`（`same-dir`/`worktree`/`session`）、`--capacity`（默认 32）、`--permission-mode` | 需要 claude.ai 订阅登录；API key 和 `setup-token` 生成的 token 都不能建立 Remote Control | 加分项：把 B 上的会话挂到手机上给评委看。它是给人用的界面，不适合程序化派单 | 可选 | 同左 |

### 1.7 开发与部署工具（“有什么 tools 可以用”）

| 名称 | 链接 | 做什么 | 状态 | 在本项目怎么用 | 建议 | 来源 / 安装指引 |
|---|---|---|---|---|---|---|
| Caddy | https://caddyserver.com/docs/automatic-https | 自动 HTTPS：域名的 A/AAAA 记录指向服务器，且 80/443 端口对外开放即可；对裸 IP 和内部主机名只发自签证书。`reverse_proxy` 会先做 HTTP upgrade，再把连接转成双向隧道（WebSocket 可用）；重载配置时会强制关闭 WebSocket，可用 `stream_close_delay` 延迟关闭 | 官方文档 | Lightsail 上的 Caddyfile：`<域名> { reverse_proxy localhost:8000 }` | **直接用** | https://caddyserver.com/docs/caddyfile/directives/reverse_proxy ；安装：https://caddyserver.com/docs/install |
| nip.io / sslip.io | https://nip.io/ | 把 IP 嵌在主机名里的 DNS 服务，例如 `www.192-168-0-1.nip.io` 解析为 `192.168.0.1`；可以用 HTTP-01 从 Let's Encrypt 申请证书（文档举了 Caddy 为例）；不支持通配符证书 | 第三方公共服务 | 没买域名时用 `<Lightsail静态IP>.nip.io` 作为 Caddy 站点名 | 可用 | 同左 |
| cloudflared Quick Tunnel | https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/ | `cloudflared tunnel --url http://localhost:8080` 得到一个临时的 `trycloudflare.com` 地址；**不需要账号和域名**；每个隧道最多 200 个并发请求；不支持 SSE；每次的主机名都不同；文档说明不用于生产 | 官方；页面没提 WebSocket | 本地开发时让 ESP32 或手机临时连到笔记本上的 FastAPI | 开发期用 | 同左（安装见该页面链接的下载页） |
| ngrok（免费计划） | https://ngrok.com/docs/pricing-limits/free-plan-limits/ | 最多 3 个在线 endpoint 和 3 个并发 agent；只提供 1 个自动分配的 dev 域名；每月 1GB 出站流量、20,000 个 HTTP 请求；浏览器访问 HTML 时会先显示 interstitial 警告页（可用 `ngrok-skip-browser-warning` 头跳过） | 官方 | 备选隧道（dev 域名固定，比 Quick Tunnel 稳） | 备选 | 同左 |
| AWS Lightsail | https://aws.amazon.com/lightsail/pricing/ | 带 IPv4 的 Linux 套餐：$5（0.5GB / 2 vCPU / 20GB SSD / 1TB 流量）、$7（1GB / 40GB / 2TB）、$12（2GB / 60GB / 3TB）；纯 IPv6 套餐 $3.50 起；所有套餐都包含静态 IP；**Malaysia 区域的流量额度只有表中的一半** | 区域包含 Asia Pacific (Malaysia) `ap-southeast-5`（需手动启用的 opt-in 区域）和 Singapore `ap-southeast-1` | 部署协调器（选 $7 或 $12 档） | **推荐** | 同左；https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html |
| AWS EC2 | https://aws.amazon.com/vpc/pricing/ | 公网 IPv4 无论是否在用都按 $0.005/小时计费；新账户 Free Tier：先给 $100 额度，最多可再获 $100，免费计划 6 个月后或额度用完时自动结束 | 官方 | 只在团队已有 EC2 经验时考虑 | 次选 | 同左；https://aws.amazon.com/free/ |
| 任务计划程序 `schtasks` | https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create | `/sc ONLOGON`：任意用户登录时运行；`/it`：只在 run-as 用户已登录时运行；`/delay mmmm:ss`：延迟启动；`/rl HIGHEST`：最高权限；System 账户没有交互登录权限，用户看不到它启动的程序 | 官方 | `schtasks /create /tn PhysicalAgent /tr "<python.exe> <agent.py>" /sc onlogon /it /delay 0000:30` | **推荐** | 同左 |
| NSSM | https://nssm.cc/usage | 把任意程序包装成 Windows 服务（`nssm install <服务名> <程序> [参数]`），支持退出后自动重启、`AppStdout`/`AppStderr` 重定向 | 最新正式版 2.24（2014-08-31），预发布版 2.24-101（2017-04-26）；服务运行在 Session 0，Session 0 不可交互，服务弹出的 UI 不会出现在用户会话里 | 不适合需要打开 VS Code/浏览器的 agent | **不用**（纯后台进程可以考虑） | https://nssm.cc/download ；https://learn.microsoft.com/en-us/previous-versions/bb756986(v=msdn.10) |
| uv | https://docs.astral.sh/uv/getting-started/installation/ | Python 包和项目管理 | Windows：`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` 或 `winget install --id=astral-sh.uv -e` | 协调器和 agent 的依赖管理 | **直接用** | 同左 |
| FastAPI | https://fastapi.tiangolo.com/advanced/websockets/ | `@app.websocket("/ws")`，连接断开时 `receive_text()` 抛出 `WebSocketDisconnect`；WebSocket 端点可用 `Depends`/`Query`/`Header`/`Cookie` 做认证，认证失败时抛 `WebSocketException(code=WS_1008_POLICY_VIOLATION)`；文档用 `uv add websockets` 添加依赖 | PyPI 0.164.0，Python ≥3.11 | 协调器：设备 WSS 端点 + artifact HTTP 端点 | **直接用** | 同左；https://pypi.org/pypi/fastapi/json |
| websockets（Python） | https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html | `async for websocket in connect(...)` 遇到暂时性错误时按指数退避自动重连；`additional_headers` 可在握手时带 token；`ping_interval`/`ping_timeout` 默认都是 20 秒；默认使用系统代理 | PyPI 17.4，Python ≥3.11，BSD-3-Clause | device agent 的出站 WSS 客户端 | **直接用** | 同左；https://pypi.org/pypi/websockets/json |
| httpx | https://pypi.org/project/httpx/ | Python HTTP 客户端 | PyPI 0.28.1，Python ≥3.8，BSD-3-Clause | agent 上传和下载 artifact | 直接用 | https://pypi.org/pypi/httpx/json |
| Playwright（Python） | https://playwright.dev/python/docs/intro | `pip install pytest-playwright` 后运行 `playwright install`；系统要求 Windows 11+、Windows Server 2019+ 或 WSL（**文档没有列出 Windows 10**） | 官方 | 在 B 上验证生成的网页能打开、没有报错，然后再通知用户确认 | 可选 | 同左 |
| Playwright MCP | https://github.com/microsoft/playwright-mcp | 基于可访问性快照（不依赖截图）的浏览器 MCP；`claude mcp add playwright npx @playwright/mcp@latest`；需要 Node.js 20+；选项有 `--headless`、`--browser`、`--isolated`、`--caps`；README 建议编码代理优先用 Playwright CLI + skills（更省 token）；还写明“它不是安全边界” | Apache-2.0 | 让 B 上的 Claude 自测网页（作为加分项） | 可选 | 同左 |
| ESP-IDF | https://github.com/espressif/esp-idf/releases | 最新稳定版 v6.1.1（11-16）；还在维护的分支有 v5.5.6（10-16）、v6.0.3（09-02）等。官方建议新项目用仍处于 Service 期的最新稳定版；每个版本支持 30 个月 | 官方 | 唤醒棒固件：v6.1.1 或 v5.5.x，配 esp_tinyusb 3.0.1（esp_tinyusb 3.0.0 起要求 IDF ≥ 5.3） | **直接用** | 同左；https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/versions.html |
| esp_websocket_client | https://components.espressif.com/components/espressif/esp_websocket_client | ESP-IDF 的 WebSocket 客户端：支持 `ws`/`wss`（mbedTLS，提供 `cert_pem` 才校验服务器证书）、ping/pong（默认 10 秒一次）、默认开启自动重连（默认间隔 10 秒）、自定义请求头（可放认证 token） | 1.8.0，支持所有芯片 | ESP32 唤醒棒直接通过 WSS 连协调器（与已定架构一致） | **直接用** | 同左；https://docs.espressif.com/projects/esp-protocols/esp_websocket_client/docs/latest/index.html |
| ESP-MQTT | https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/protocols/mqtt.html | 支持 MQTT v5.0；从 IDF v6.0 起移出 IDF 主仓库，用 `idf.py add-dependency espressif/mqtt` 添加 | 官方 | 只在改用 MQTT 时需要 | 备选 | 同左 |
| Mosquitto | https://mosquitto.org/download/ | MQTT broker，最新 2.1.4，提供 Windows x64/x86 安装包 | 仓库根目录有 `edl-v10`、`epl-v20` 两个许可证文件（页面未明说许可证名称） | 只在改用 MQTT 时需要 | 备选 | 同左；https://github.com/eclipse-mosquitto/mosquitto |
| EMQX | https://github.com/emqx/emqx | MQTT broker | 原文：从 5.9.0 起许可证由 Apache 2.0 改为 BSL 1.1 | — | 不用（我们不需要 broker） | 同左 |
| Agora CLI | https://docs.agora.io/en/introduction/agora-cli | 登录、用官方 starter 初始化项目（`agora init <name> --template nextjs/python/go`）、写入环境变量、`agora project doctor` 自检；文档示例是 conv-ai 教程 | MIT，Go 编写；Windows 10+ 有预编译版本：`irm https://dl.agora.io/cli/install.ps1 \| iex` | 只有在语音前端用 Agora 时才相关（不属于本文范围） | 视语音方案而定 | 同左；https://github.com/agoraio/cli |
| powercfg | https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options | `/a`、`/devicequery wake_armed`、`/deviceenableawake`、`/devicedisablewake`、`/lastwake`、`/waketimers`、`/requests`、`/sleepstudy`、`/spr`、`/setacvalueindex`、`/aliases` | Windows 自带 | 唤醒可行性测试与现场排障（见 §2.1） | **必用** | 同左 |

**MQTT 还是 WSS（ESP32）？** 建议维持 WSS 直连 FastAPI：esp_websocket_client 已支持 wss、心跳、自动重连和自定义请求头，不需要再部署一个 broker。只有当团队已有 MQTT 经验时才考虑 MQTT。MeshCentral 也支持设备用 MQTT 接收 `powerAction`（见 §1.2），说明这种模式可行，但不是必需的。

---

## 2. 关键事实

### 2.1 Windows：睡眠、唤醒、锁屏（只引用微软文档）

**A. 两种睡眠模型**
- Windows 10 起有两种电源模型：S3 和 Modern Standby。Modern Standby 在待机时仍处于 S0，可以“保持联网”或“断网”待机。文档还写道：“a wake on LAN would be expected to work the same way on a Modern Standby system and an S3 system”，前提是设备进入 D3 时已被设置为可唤醒（armed）。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/modern-standby-vs-s3
- `powercfg /availablesleepstates`（`/a`）会列出可用的睡眠状态，并尝试说明不可用的原因。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options

**B. Modern Standby 下软件如何被冻结（直接影响 agent）**
- 屏幕关闭后依次经过这些阶段：NoCS → Connection → PLM → Maintenance → DAM → Low-power → Resiliency notification → Resiliency。DAM 阶段会暂停桌面应用；原文说 “Windows prevents desktop applications from running during any part of modern standby after completing the DAM phase”。Resiliency 阶段 Session 0 服务被限流到“每 30 秒不超过 1 秒”；24H2 起还可能进一步挂起 Session 0 服务。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/prepare-software-for-modern-standby
- 应用持有的电源请求在 AC 下会**无限期**阻止 NoCS 阶段结束，在 DC 下**最多 5 分钟**。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/prepare-software-for-modern-standby
- 网络安静模式（NQM）：Modern Standby 期间，第三方系统服务看到的 Wi-Fi 就像断开了一样；除了用户固定到锁屏的商店应用，远程访问在 Modern Standby 期间都不可用。网卡如果同时不支持协议卸载和 WoL patterns，会在 Modern Standby 期间被禁用；有以太网时 Windows 优先使用以太网。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/networking-power-management-for-modern-standby-platforms

**C. 待机时联网与 WoL（方案 1 的可行性）**
- Windows 10 2004 起默认使用 **Adaptive Connected Standby（ACS）**：电池供电时，只有用户启用了远程桌面，或把某个需要后台联网的 UWP 应用设为“始终”在后台运行，睡眠时才保持联网；否则静默网络。可以看 `powercfg /spr` 报告里的 “Networking in standby” 字段确认。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/modern-standby-network-connectivity
- 旧设置 “Allow networking during standby”（`ConnectivityInStandby`，GUID `f15576e8-98b7-4186-b944-eafa664402d9`）**从 Windows 10 2004 起已弃用**。https://learn.microsoft.com/en-us/windows-hardware/customize/power-settings/no-subgroup-settings-allow-networking-during-standby
- 进入断网待机时，LAN、Wi-Fi、MBB 都不配置唤醒 pattern，并且会向 Wi-Fi 发送 media disconnect。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/networking-power-management-for-modern-standby-platforms
- 唤醒源表：**“Wi-Fi radio”属于“唤醒 SoC 但不能点亮屏幕”**，且“Disconnected Standby 系统不要求 Wi-Fi 唤醒源”。远程桌面和文件共享的唤醒只在以太网下可用。Windows 在网络上检测到关键告警（如高优先级通知、VoIP 来电）时可以点亮屏幕。DC 供电时网络栈可能主动断开 Wi-Fi。**24H2 起，若检测到异常耗电，大多数唤醒源会被禁用，只能按电源键或开盖唤醒。** https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/modern-standby-wake-sources
- 网卡驱动的标准 INF 关键字：`*WakeOnMagicPacket`（默认 1，启用）、`*WakeOnPattern`（默认启用）、`*PMWiFiRekeyOffload`（WoWLAN 时把 GTK 重协商卸载给网卡，默认启用）。还有 **`*ModernStandbyWoLMagicPacket`：“系统处于 S0ix 时收到魔术包就唤醒”，默认 0（Disabled）**，适用于 NDIS 6.60 / Windows 10 1607 起的传统 NDIS 驱动，S4 下不适用。https://learn.microsoft.com/en-us/windows-hardware/drivers/network/standardized-inf-keywords-for-power-management
- Wake-on-Wireless-LAN（Native 802.11 文档，NDIS 6.20 起；Windows 10 起该接口已弃用，改用 WDI）：网卡必须处于基础设施（Station）模式，并以 WPA2 或 WPA2-PSK 关联到 AP；低功耗时由网卡处理 GTK 重协商。https://learn.microsoft.com/en-us/previous-versions/windows/hardware/wireless/wake-on-wireless-lan
- WoL 总体规则（支持文章，2026-02 更新）：Windows 10 只支持从睡眠（S3）或用户主动休眠（S4）唤醒；快速启动的混合关机（S4）和 S5 不支持，因为这些情况下网卡明确不会被设置为可唤醒。https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/wake-on-lan-feature
- Surface 官方：Modern Standby 下的 WoL 要求**接 AC 电源，并使用接入有线网络的以太网适配器或扩展坞**。https://learn.microsoft.com/en-us/surface/wake-on-lan-for-surface-devices
- Wi-Fi 设备要在 Modern Standby 下保持连接，需要支持 NDIS 6.3 的 WoL patterns、协议卸载和 D0 packet coalescing。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/modern-standby-wi-fi-connected-scenarios

**D. USB 键盘唤醒（方案 2 的可行性）**
- 外接 USB 键盘：能唤醒 SoC 并点亮屏幕（AC 和 DC 下都标为 Yes，带注释）。原文：“Multiple key presses might be needed to generate a resume event”；“Keyboard wake may be disabled to save battery”。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/modern-standby-wake-sources
- 24H2 起，合盖（clamshell）时启用输入抑制，屏幕不会点亮；接了外接显示器时不启用。同上。
- 用 `powercfg /devicequery wake_armed` 查看当前允许唤醒的设备，用 `powercfg /deviceenableawake "<设备名>"` 启用（官方文档里的拼写就是 `deviceenableawake`），用 `powercfg /lastwake` 查看上次的唤醒源。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options

**E. “System unattended sleep timeout”（无人值守唤醒后多久再睡）**
- 定义：系统因定时事件或 WoL 等方式“无人值守”地从睡眠唤醒后，使用这个值，而不是普通的睡眠空闲超时。单位是秒，0 表示永不自动睡眠；属于隐藏设置；GUID `7bc4a2f9-d8fc-4469-b07b-33eb785aaca0`；PowerCfg 别名 `UnattendTimeout`；适用于 Vista SP1 及以后。**微软页面没有写默认值。** https://learn.microsoft.com/en-us/windows-hardware/customize/power-settings/sleep-settings-sleep-unattended-idle-timeout
- 对应的 Policy CSP：`UnattendedSleepTimeoutOnBattery` 和 `UnattendedSleepTimeoutPluggedIn`（Windows 10 1903+；适用版本列 Pro/Enterprise/Education/IoT）。https://learn.microsoft.com/en-us/windows/client-management/mdm/policy-csp-power
- 实操：由于是隐藏设置，修改时用别名，例如 `powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP UnattendTimeout 600`。这里的 `SUB_SLEEP` 子组别名**是推断的**，应先用 `powercfg /aliases` 和 `powercfg /query` 在实机上确认。文档原文是：“These aliases may be used instead of a GUID in any command”。https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options

**F. 用 SetThreadExecutionState 保持唤醒**
- 标志位：`ES_SYSTEM_REQUIRED (0x1)` 重置系统空闲计时器；`ES_DISPLAY_REQUIRED (0x2)` 重置显示器空闲计时器；`ES_CONTINUOUS (0x80000000)` 让设置一直生效到下次调用；`ES_AWAYMODE_REQUIRED (0x40)` 必须与 `ES_CONTINUOUS` 一起用，只应给媒体类应用使用，便携电脑不应启用；`ES_USER_PRESENT` 不受支持，与其他标志一起用会导致调用失败。
- 原文：后台代理、网络管理类应用在处理事件时“must use both ES_SYSTEM_REQUIRED and ES_CONTINUOUS”；“cannot be used to prevent the user from putting the computer to sleep”（合盖和按电源键仍然有效）；不带 `ES_CONTINUOUS` 调用只会重置一次计时器。https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate
- 用 `powercfg /requests` 可以确认 agent 的请求是否生效。在 Modern Standby 下，电源请求在 AC 时无限期有效、DC 时最多 5 分钟（见 B）。

**G. 唤醒后是否需要登录**
- 电源设置 “Prompt for password on resume”：别名 `CONSOLELOCK`，GUID `0e796bdb-100d-47d6-a2d5-f7d2daa51f51`，隐藏设置，不属于任何子组。**所有 Windows 桌面版默认启用**。0 表示回到桌面，1 表示回到安全桌面并要求输入密码。https://learn.microsoft.com/en-us/windows-hardware/customize/power-settings/no-subgroup-settings-prompt-for-password-on-resume
- Policy CSP `RequirePasswordWhenComputerWakesOnBattery` / `PluggedIn`：启用或未配置时唤醒需要密码，禁用时不需要；适用版本列 Pro/Enterprise/Education/IoT Enterprise，**不含 Home**。https://learn.microsoft.com/en-us/windows/client-management/mdm/policy-csp-power
- 家庭版的做法（**推断**，官方页面没有给出这条命令）：`powercfg /setacvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 0`，然后 `powercfg /setactive SCHEME_CURRENT`。依据：微软 Surface 文档用过同样形式的 `powercfg /SETACVALUEINDEX SCHEME_BALANCED SUB_NONE CONNECTIVITYINSTANDBY 1`（https://learn.microsoft.com/en-us/surface/wake-on-lan-for-surface-devices ）。Windows Hello / 动态锁等其他设置也可能要求重新登录，未核实。

**H. agent 应在哪种进程环境里运行**
- Vista 起，服务运行在 Session 0，而 Session 0 是非交互的；服务弹出的 UI 不会显示在用户会话中；需要复杂 UI 时应在用户会话中用 `CreateProcessAsUser` 创建进程。https://learn.microsoft.com/en-us/previous-versions/bb756986(v=msdn.10)
- 计划任务：`/sc ONLOGON` 加 `/it` 可以让程序在用户登录后、在该用户的会话里运行；System 账户“没有交互登录权限”。https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create

**I. 建议的 A/B 实机测试清单（每台约 30 分钟）**
1. `powercfg /a` 看是否为 Modern Standby（S0 Low Power Idle）。
2. 在网卡“高级”属性里查找 “Wake on magic packet” 和 “Wake on magic packet when system is in the S0ix power state” 这类选项（名称来自上面的 INF 关键字 ParamDesc），并在“电源管理”页允许唤醒。
3. 接 AC、合盖或开盖各测一次：从同一路由器下的另一台设备（或 UpSnap）发魔术包，再用 `powercfg /lastwake` 和 `powercfg /spr` 查看。
4. 同时观察：Python agent 的 WSS 是否自动重连，屏幕是否点亮，锁屏是否出现。
5. 方案 2：插上 ESP32-S3，用 `powercfg /devicequery wake_armed` 确认它出现在列表中，然后测试从 Modern Standby 唤醒。

### 2.2 ESP32 USB HID remote wakeup：现状

- **TinyUSB 的条件**：`tud_remote_wakeup()` 只有在设备**已挂起**且**主机已通过 SET_FEATURE 允许远程唤醒**时才会发送 resume 信号，否则直接返回 false。主机在恢复后可能用 CLEAR_FEATURE 关掉这个许可。挂起时 `tud_suspend_cb(remote_wakeup_en)` 会把当前许可状态传给应用；挂起后设备必须在 7ms 内把平均电流降到 2.5mA 以下。https://raw.githubusercontent.com/hathach/tinyusb/master/src/device/usbd.c ，https://raw.githubusercontent.com/hathach/tinyusb/master/src/device/usbd.h
- **esp_tinyusb 的 API**：`esp_err_t tinyusb_remote_wakeup(void);`。注释原文：“Call this function only while the device is suspended and the host has enabled remote wakeup”。返回值：`ESP_ERR_INVALID_STATE` 表示驱动未安装或主机未允许远程唤醒；`ESP_ERR_NOT_ALLOWED` 表示设备未挂起；`ESP_FAIL` 表示信号发送失败。挂起事件 `TINYUSB_EVENT_SUSPENDED` 的 `suspended.remote_wakeup` 字段（bool）表示主机是否已允许。https://raw.githubusercontent.com/espressif/esp-usb/master/device/esp_tinyusb/include/tinyusb.h
- **是否已在正式版本中：是。** PR #387 “feat(esp_tinyusb): Added device suspend/resume events” 于 2026-02-02 合并，新增 `tinyusb_remote_wakeup()` 的声明和实现，里程碑从 v2.0.2 改为 v2.1.0（https://github.com/espressif/esp-usb/pull/387 ；文件差异：https://api.github.com/repos/espressif/esp-usb/pulls/387/files ）。随后 release PR #394 “release(esp_tinyusb): v2.1.0” 于 2026-02-05 合并（https://github.com/espressif/esp-usb/pull/394 ）。组件注册表上有 2.1.0 版本页，它的 README 写到了 suspend/resume 事件（默认关闭，需 Kconfig 开启），但**没有提到 `tinyusb_remote_wakeup` 这个名字**（https://components.espressif.com/components/espressif/esp_tinyusb/versions/2.1.0 ）。当前最新版 3.0.1 的头文件里有这个 API。
- **版本差异**（CHANGELOG）：2.1.0 “Added configurable Suspend/Resume device event support”。3.0.0 是破坏性变更：suspend/resume 回调总是在 esp_tinyusb 内部注册，相关 Kconfig 被删除，应用必须通过设备事件回调处理 SUSPENDED/RESUMED，不能自己定义 `tud_suspend_cb()`/`tud_resume_cb()`；同时不再支持 ESP-IDF < 5.3。3.0.1 修复了“重复或过期的 Suspend 事件”。https://raw.githubusercontent.com/espressif/esp-usb/master/device/esp_tinyusb/CHANGELOG.md
- **历史**：更早的 PR #252 也想加 `tinyusb_remote_wakeup()`，2025-09-18 因为会破坏已发布版本而关闭。https://github.com/espressif/esp-usb/pull/252
- **官方文档补充**：可选的 PM 锁会在 suspend 时释放、resume 时重新获取；全速（FS）端口的 USB 设备外设**不能**作为 light sleep 的唤醒源（这是 ESP32 自身的睡眠唤醒，和 remote wakeup 是两回事）。https://docs.espressif.com/projects/esp-usb/en/latest/esp32s3/usb_device.html
- **nonoo/esp-remote-wakeup 的做法**：基于旧版 esp_tinyusb 1.3.1，直接调用 TinyUSB 的 `tud_remote_wakeup()`；调用前只检查 `tud_mounted()`，不检查是否挂起。见 §1.1。
- **Arduino 路线的问题**：arduino-esp32 #10831（ESP32-S3、core 3.1）中，`USBHIDKeyboard` 在 PC 睡眠后从不进入 suspend，收不到 SUSPENDED/RESUMED 事件，`tud_suspended()` 一直为 false，所以无法唤醒。issue 于 2026-10-14 以“refers to an older version”关闭，没有指明修复版本。https://github.com/espressif/arduino-esp32/issues/10831
- **落地建议**（基于以上事实推导）：ESP-IDF v5.5.x 或 v6.1.x + esp_tinyusb 3.0.1，基于 HID 键盘示例；配置描述符设置 REMOTE_WAKEUP 属性；在 SUSPENDED 事件里记录 `remote_wakeup`；收到云端 `wake` 指令后调用 `tinyusb_remote_wakeup()`。若返回 `ESP_ERR_INVALID_STATE`，说明主机没有允许远程唤醒，应检查 Windows 设备管理器的电源管理选项和 `powercfg /devicequery wake_armed`（这两者如何对应**未核实**）。鉴于微软文档说“可能需要多次按键”，可以在 RESUMED 后再补发一个无害按键（例如 Shift）让屏幕亮起（**推断**，需实测）。

### 2.3 Claude Code 作为 B 的编码代理

**无头运行（https://code.claude.com/docs/en/headless ）**
- `claude -p "<prompt>"`：成功退出码为 0，失败为非 0；运行中的失败（例如没有认证）会作为结果打印到 stdout。用 SIGTERM 终止时退出码为 143。通过管道输入的 stdin 上限 10MB。
- 输出格式：`--output-format text`（默认）、`json`（含 `result`、`session_id`、`total_cost_usd` 等字段）、`stream-json`（换行分隔的 JSON 事件，流式输出需加 `--verbose`，要逐 token 输出再加 `--include-partial-messages`，最后一行是 `result` 消息）。`--json-schema` 配合 `--output-format json` 时，结果放在 `structured_output` 字段。
- **权限**：v2.1.302 起，没有设置权限模式的 `-p` 运行从 Manual 模式开始，需要审批的调用会被拒绝。可以用 `--permission-mode` 设基线（`acceptEdits`：写文件和常见文件系统命令自动批准；`dontAsk`：所有本该提示的调用都拒绝；`auto`：由分类器审查），也可以用 `--allowedTools "Read,Edit,Write,Bash(npm *)"` 等逐项放行。`--permission-prompts none`（v2.1.259+）告诉 Claude 没有人能审批，不要重试被拒的调用。`--dangerously-skip-permissions` 等同于 `bypassPermissions`。
- **`--bare`**：跳过 hooks、skills、插件、MCP、CLAUDE.md 等的自动发现，适合脚本。但 bare 模式**不读取 OAuth/订阅凭据，也不读取 `CLAUDE_CODE_OAUTH_TOKEN`**，必须用 `ANTHROPIC_API_KEY` 或 `apiKeyHelper`。文档写明 bare “will become the default for `-p` in a future release”。→ 用订阅 token 时，演示前应锁定 Claude Code 版本（`settings.json` 的 `env` 里设 `DISABLE_AUTOUPDATER=1`，见 https://code.claude.com/docs/en/setup.md ）。
- 不加 `--bare` 时，`-p` 会运行项目 `.claude/settings.json` 里的 hooks，并连接 `.mcp.json` 中的服务器，而且不弹信任对话框 → B 应在固定的、干净的工作目录里运行。

**CLI 参数（https://code.claude.com/docs/en/cli-reference ）**
- `--tools "Bash,Edit,Read"`：限制可用的内置工具（`""` 表示全部禁用，`"default"` 表示默认集合）。`--allowedTools` 只是免提示放行，不限制工具集合。`--disallowedTools` 是拒绝规则，写成 `"mcp__*"` 可以去掉所有 MCP 工具。
- `--restricted`（v2.1.248+）：除非在 `--tools` 里逐个点名，否则移除执行命令或代码的内置工具和 WebFetch；文件工具限制在工作目录内；只加载托管设置和 `--settings`；拒绝 `bypassPermissions`。**这和“生成网页后要运行或测试”相冲突，本项目一般不用。**
- `--max-budget-usd 5.00`：只在 print 模式下有效，基于客户端的费用估算，实际花费**可能超过**上限（要留余量），子代理的花费也算在内；达到上限时停止后台子代理（相关行为需 v2.1.217+）。另有 `--max-turns N`（只在 print 模式有效）。
- 其他：`--no-session-persistence`（不保存会话）、`--add-dir`、`--append-system-prompt`、`--mcp-config`、`--settings`、`--input-format stream-json`（多轮流式输入）。

**认证（https://code.claude.com/docs/en/authentication ）**
- 优先级：云厂商变量 > `ANTHROPIC_AUTH_TOKEN` > `ANTHROPIC_API_KEY`（**在 `-p` 下只要存在就一定使用**）> `apiKeyHelper` > `CLAUDE_CODE_OAUTH_TOKEN` > Anthropic profile > `/login` 的订阅凭据。
- `claude setup-token`：在浏览器授权后打印一个**一年期**的 OAuth token，命令本身不保存它；需要 Pro/Max/Ultra/Team/Enterprise 订阅；用环境变量 `CLAUDE_CODE_OAUTH_TOKEN` 提供（PowerShell：`$env:CLAUDE_CODE_OAUTH_TOKEN = "…"`）。这个 token **只能发模型请求**，不能建立 Remote Control，也不能获取 claude.ai connectors。
- Windows 凭据保存在 `%USERPROFILE%\.claude\.credentials.json`。
- 注意：如果 B 上同时有 `ANTHROPIC_API_KEY`，`-p` 会优先使用 API key（按 API 计费）。

**Agent SDK（Python）比 CLI 多了什么**
- `pip install claude-agent-sdk`（PyPI 0.2.184，Python ≥3.10），包内自带 CLI。提供 `query()` 异步迭代器和 `ClaudeSDKClient`（双向对话，支持自定义工具和 hooks）；自定义工具以进程内 MCP 服务器形式实现（`@tool` + `create_sdk_mcp_server`）；hooks 是 Python 函数（例如在 `PreToolUse` 时拒绝危险的 Bash 命令）；有类型化的消息对象和错误类型。https://github.com/anthropics/claude-agent-sdk-python ，https://pypi.org/pypi/claude-agent-sdk/json
- 官方说明：除非事先获批，Anthropic 不允许第三方开发者在自己的产品里（包括基于 Agent SDK 构建的 agent）提供 claude.ai 登录或订阅额度，应使用 API key 认证。https://code.claude.com/docs/en/agent-sdk/overview.md

**能否从另一台机器控制会话**
- **Remote Control**：`claude remote-control`（服务器模式）或 `claude --remote-control`。本机只发出站 HTTPS（端口 443）请求，不开入站端口；从 claude.ai/code 或 Claude App 连接。要求 Pro/Max/Ultra/Team/Enterprise 订阅，“API keys are not supported”，`setup-token` 生成的 token 也不行；不能配合 Bedrock、Vertex、Foundry 或自定义 `ANTHROPIC_BASE_URL` 使用。服务器参数有 `--spawn same-dir`/`worktree`/`session`、`--capacity`（默认 32）、`--permission-mode`、`--name`。https://code.claude.com/docs/en/remote-control
- **VS Code 扩展**：`vscode://anthropic.claude-code/open?prompt=…`（只预填，不提交）和 `session=<id>`（恢复 VS Code 当前打开文件夹中的会话）。设置项 “Enable Remote Control for all sessions”（`remoteControlAtStartup`）。https://code.claude.com/docs/en/vs-code
- **`claude-cli://open?cwd=…&q=…`**：在本机新终端中打开会话并预填 prompt，不自动执行。https://code.claude.com/docs/en/deep-links
- 其他：`--bg` 后台会话和 `claude agents`（agent view）、`--cloud`/`--teleport`（云会话）。这些对本项目不是必需的。https://code.claude.com/docs/en/cli-reference

**推荐的 B 端命令（基于以上事实组合，需实测）**
```powershell
$env:CLAUDE_CODE_OAUTH_TOKEN = "<setup-token 生成的 token>"   # 或改用 ANTHROPIC_API_KEY（此时可加 --bare）
claude -p (Get-Content prompt.md -Raw) `
  --output-format stream-json --verbose `
  --permission-mode acceptEdits `
  --allowedTools "Read,Edit,Write,Bash(npm *),Bash(npx *)" `
  --permission-prompts none `
  --max-turns 30 --max-budget-usd 3
```

---

## 3. 未能核实

1. **团队 A/B 笔记本的 Wi-Fi 网卡在 Modern Standby 下能否被魔术包唤醒。** 微软文档只说明了机制和默认值（`*ModernStandbyWoLMagicPacket` 默认关闭、Wi-Fi 唤醒源不点亮屏幕、Surface 要求以太网）。具体网卡（WDI 驱动）是否提供这个选项、是否生效，只能实机测试。
2. **Modern Standby 下 Wi-Fi WoL 只唤醒了 SoC 时，被 DAM 暂停的桌面 agent 会不会恢复运行**（也就是系统会不会真正退出待机）。微软文档没有直接说明。
3. **“System unattended sleep timeout 默认约 2 分钟”**：只在第三方页面看到，微软页面没写默认值；该设置在 Modern Standby 下的具体行为也没写。
4. **ESP32-S3 + esp_tinyusb 的 remote wakeup 在 Windows Modern Standby 笔记本上能否成功**：nonoo 项目的排障说明只覆盖 Linux。Windows 设备管理器里的“允许此设备唤醒计算机”与主机的 SET_FEATURE(REMOTE_WAKEUP) 是否一一对应，没有找到微软原文。
5. **esp_tinyusb / esp-usb 的许可证**：本次没有打开 LICENSE 文件核对。
6. **锁屏状态下，用户会话里已运行的 agent 和 `claude -p` 能否照常运行、`Start-Process` 打开的窗口是否会在解锁后出现**：没有找到微软原文，需要实测。
7. **Windows 家庭版下关闭“唤醒需密码”的确切做法**：powercfg `SUB_NONE CONSOLELOCK 0` 是根据别名机制推断的；设置界面的路径只在第三方页面出现；Windows Hello 等是否另外强制锁屏也未核实。
8. **`UnattendTimeout` 所在子组的别名（是否为 `SUB_SLEEP`）**：需用 `powercfg /aliases` 在实机上确认。
9. **UFO³ Galaxy 跨公网部署**：文档示例都是 localhost，只写了“设备之间需要网络互通”。server/client 能否分开部署、client 能否出站连到云端 server，未核实。
10. **OpenClaw 的文件传输能力和 Gateway 公网暴露建议**：node host 页面没有文件传输命令；protocol 索引页没有写公网暴露的建议。
11. **发布年份**：MeshCentral 1.3.1（10 月 23 日）、Tactical RMM v1.6.1（10 月 27 日）、HASS.Agent 2.2.1（6 月 7 日）、pywinauto 0.6.9（1 月 6 日）的发布页都没显示年份。
12. **用 headless `-p` 生成的会话能否通过 VS Code URI 的 `session=<id>` 恢复显示**：文档只说“恢复 VS Code 当前打开文件夹中的会话”，没有专门提到 `-p` 会话。
13. **Lightsail 免费试用的具体条款，以及 Let's Encrypt 是否直接签发 IP 证书**：定价页只指向 Free Tier FAQ；Caddy 文档只说 IP 证书“只有部分 CA 提供”。
14. **Playwright 是否支持 Windows 10**：官方系统要求只列了 Windows 11+、Server 2019+ 和 WSL。
15. **Mosquitto 的确切许可证名称**：只看到仓库里有 `epl-v20`、`edl-v10` 两个文件。
16. **ESP32-S3 开发板上两个 USB 口哪个是 OTG（用于 TinyUSB 设备模式）**：Espressif 开发板用户指南链接返回 404，本次没有核实。
17. **Wake-on-WLAN 文档中的 WPA2 要求是否同样适用于 WDI 驱动和 WPA3 路由器**：该文档是 Native 802.11 的存档页。旅行路由器建议设为 WPA2-PSK 并关闭 AP 隔离（后者来自 LocalSend 排障表，用于说明设备间直连的条件）。
