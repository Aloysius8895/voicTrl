# 01 语音入口与穿戴硬件调研

- 调研日期：2026-11-18（比赛 2026-11-28）
- 范围：Agora Conversational AI 的工具调用与主动播报、Agora 官方样例仓库、Agora 在 ESP32 上的方案、ESP-Mosaico / ESP-Claw、xiaozhi-esp32 生态，以及其他开源 ESP32 语音栈（只作兜底参考）。
- 方法：只认一手来源（docs.agora.io、GitHub 仓库 README 与源码、Espressif 官方文档与数据手册、PyPI JSON API）。“最近活动”取自各仓库 `commits/<branch>.atom` 的最新提交时间或 GitHub API 的 `pushed_at`，查询时间为 2026-11-18。
- 一处自行核验：下载了 `agora_iot_sdk.tar`，只读取其中 `.a` 静态库的 ELF 头，没有编译或运行任何东西（详见“关键事实 4.4”）。

---

## 对本项目最有用的 5 个

1. **Agora REST `llm.mcp_servers`（Use MCP tools）**：托管 LLM 通过 streamable HTTP 直接调用协调器上的 MCP 端点，支持自定义 `headers`（可放 `Authorization`），正好对上“托管 LLM 调协调器工具”的架构。<https://docs.agora.io/en/ai/build/tools/mcp-tools>
2. **Agora `POST .../agents/{agentId}/think` 和 `/speak`**：协调器在 B 生成完网页后主动让 agent 开口；工具调用只能同步、最长 100 s，所以“工具立刻返回 + 完成后 `/think` 回报”是必须的模式。<https://docs.agora.io/en/api-reference/api-ref/conversational-ai/think>
3. **AgoraIO-Conversational-AI/recipe-agent-mcp**（MIT）：FastAPI 后端，FastMCP 挂在同进程 `/mcp`，前端是 Next.js；Pipeline 模式不需要自带 LLM key。可以直接当手机网页语音入口和启动 agent 的后端骨架，把 ngrok 换成 AWS 上的 HTTPS 域名即可。<https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp>
4. **AgoraIO-Conversational-AI/recipe-agent-voice-coder**（MIT，Python）：Agora 官方做的“语音控制本地 Claude Code / Codex”，走 MCP Work 工具和 ACP，完成后用 `/think` 回报，和我们的流程几乎一样。它只认证了 macOS Apple Silicon，所以借它的架构，不直接跑。<https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder>
5. **esp-mosaico/esp-mosaico-bsp**（Apache-2.0）：比赛当天给 Mosaico 写固件的唯一官方起点。里面有 `voice_wake_cmd`（离线唤醒词）、按键、Wi-Fi，还有 `usb_extend_screen` 示例，证明 ESP32-S31 能在 Windows 上做 USB HID 设备，可作为 USB 唤醒棒的依据。<https://github.com/esp-mosaico/esp-mosaico-bsp>

三条决策警示：
- **Agora 的 ESP32 SDK 跑不了 Mosaico**。`agora_iot_sdk.tar` 里的库全是 Xtensa 架构，ESP32-S31 是 RISC-V，见 4.4。
- **Mosaico 自带的 ESP-Claw 能当 MCP 客户端，但条件很弱**：不能带 Authorization 头，默认对 LLM 不可见，见 4.2。
- **兜底方案**：xiaozhi-esp32 已经有 `BOARD_TYPE_ESP_MOSAICO` 板型，但它走的是小智服务端，不是 Agora。

---

## 问题 1：Agora Conversational AI 的工具调用与主动播报

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / 平台） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| Custom tools（REST `llm.tools` / `mllm.tools`） | https://docs.agora.io/en/ai/build/tools/custom-tools | Agora 引擎直接向你声明的 HTTPS 端点发 GET/POST 请求，把结果交给 LLM | 商业云服务；`llm.tools` 于 v2.12（2026-09-10）加入，`mllm.tools` 于 v2.13（2026-09-25）加入 | MCP 出问题时的备选：协调器开 `POST /tools/wakeLaptop` 这类端点 | 备选（参考） | 同左；https://docs.agora.io/en/ai/release-notes |
| MCP tools（REST `llm.mcp_servers` / `mllm.mcp_servers`） | https://docs.agora.io/en/ai/build/tools/mcp-tools | Agora 云端作为 MCP 客户端，以 streamable HTTP 调用你的 MCP 服务器 | `llm.mcp_servers` 于 v2.4（2026-02-02）加入，`mllm.mcp_servers` 于 v2.12 加入（只能走 REST），v2.13 起 SDK 也支持 | **主方案**：协调器（FastAPI）挂 FastMCP `/mcp`，带 Bearer 头 | 直接用 | 同左；https://docs.agora.io/en/api-reference/api-ref/conversational-ai/join |
| Broadcast a message using TTS（`/speak`） | https://docs.agora.io/en/api-reference/api-ref/conversational-ai/speak | 让 agent 直接念一段文字，不经过 LLM | 不支持 `mllm` 配置 | 播报固定的进度提示，比如“B 已唤醒”“网页已打开” | 直接用 | 同左 |
| Send a custom instruction（`/think`） | https://docs.agora.io/en/api-reference/api-ref/conversational-ai/think | 把一段文字当作用户输入注入会话，由 LLM 组织回答 | 文档没写 MLLM 限制 | 任务完成后注入“结果已在 B 的 VS Code 打开，请询问用户是否确认”，让 LLM 自然地说出来并接着做语音确认 | 直接用 | 同左 |
| 其他 REST：`interrupt` / `update` / `history` / `query` | https://docs.agora.io/en/api-reference/api-ref/conversational-ai | 打断、运行时改配置、取历史、查状态 | 同上 | `interrupt` 可用于紧急停止 | 参考 | 同左 |
| 客户端 toolkit 的 `speak` / `think` 方法 | https://docs.agora.io/en/ai/release-notes | v2.12 起 Android、iOS、Web toolkit 提供 `speak` 和 `think`，经 RTM 发送 | 同上 | 手机网页上的按钮（例如“确认”）可直接注入 | 参考 | 同左 |
| Filler words（`properties.filler_words`） | https://docs.agora.io/en/api-reference/api-ref/conversational-ai/join | 等待 LLM 或工具时播放垫话 | 默认关闭；默认等待阈值 1500 ms | 工具调用期间避免冷场 | 直接用 | 同左；https://docs.agora.io/en/ai/build/tools/custom-tools |
| Agent Studio “Custom Tools”（控制台无代码版） | https://docs.agora.io/en/ai/studio/build/custom-tools | 在控制台 Integrations 里配置 HTTP 工具 | 和 REST 版是不同入口，限制也不同（见 1(a)） | 我们用 REST 启动 agent，用不到它 | 不用 | 同左 |
| `agora-agents`（Python Agent Server SDK） | https://pypi.org/project/agora-agents/ | Python 封装的 join、tools、MCP、MLLM 接口 | PyPI 最新 2.14.0，2026-11-11 发布；Python >=3.8,<4.0；仓库 https://github.com/AgoraIO/agora-agents-python | 协调器里用它启动 agent，接口有 `.with_tools()` 和 `McpServerConfig` | 直接用 | https://pypi.org/pypi/agora-agents/json；recipe-agent-mcp 的 `server/requirements.txt` |

## 问题 2：可直接改造的 Agora 样例仓库

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / 平台） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| recipe-agent-mcp | https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp | Next.js 前端（:3000，负责 RTC/RTM）+ FastAPI 后端（:8000，负责发 token、启停 agent）+ 挂在同进程 `/mcp` 的 FastMCP。启动时在 Pipeline 或 Realtime 模式上挂 `mcp_servers`。Pipeline 模式用 Agora 托管的 Deepgram STT、OpenAI `gpt-4o-mini` 和 MiniMax TTS，“zero keys”即可跑 | MIT；创建于 2026-06-11，最近 push 2026-09-19；GitHub 标记语言为 TypeScript（前端），后端是 Python 3.10+；依赖 `agora-agents>=2.10.0`、`mcp>=1.29.0`；开发时用 ngrok，因为 `MCP_ENDPOINT` 必须公网可达、不能是 localhost | **首选骨架**：后端并入协调器，`MCP_ENDPOINT` 填 AWS 的 `https://<域名>/mcp`，再在 `McpServerConfig` 里加 headers 鉴权；手机直接打开部署后的 Next.js 页面。README 自己也提醒公开的 `/mcp` 要加鉴权 | 直接用（改造） | README；`server/src/agent.py`；`server/src/mcp_config.py`（注释写明省略 transport 时 SDK 默认用 streamable_http）；`server/requirements.txt`；https://recipes.agora.io/recipes/mcp-tools |
| recipe-agent-custom-http-tools | https://github.com/AgoraIO-Conversational-AI/recipe-agent-custom-http-tools | 演示 inline `llm.tools`：Agora 引擎直接调用 FastAPI 的 `GET /tools/orders/{id}`、`POST /tools/tickets` 等，用 `X-Tool-API-Key` 头鉴权 | MIT；最近 push 2026-09-19；Python + Next.js；同样需要公网 HTTPS（ngrok） | MCP 不稳定时，换成 custom tools 的现成样板 | 参考（备选） | README |
| recipe-agent-tool-calling | https://github.com/AgoraIO-Conversational-AI/recipe-agent-tool-calling | 走 Custom LLM：Agora 把每一轮发到你自己 `/llm` 下的 OpenAI 兼容端点，工具在你的服务器上执行，“Agora cloud never sees a tool_call” | MIT；最近 push 2026-08-17；Python + Next.js；`CUSTOM_LLM_URL` 必须公网 | 如果要完全掌控对话逻辑，可以让协调器当 Custom LLM。代价是 Agora custom tools 不支持 Custom LLM，这时工具都得自己执行 | 参考 | README；https://docs.agora.io/en/ai/build/tools/custom-tools |
| recipe-agent-voice-coder | https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder | 语音控制本地 Codex / Claude Code。托管 LLM 拿到 4 个经过鉴权的 Work 工具（start、status、cancel、permission response）；本地 FIFO 任务运行时用 SQLite，通过 ACP 驱动编码 agent；完成后把不超过 8 KiB 的 `LOCAL_WORK_COMPLETED` 信封发给 `/think`，`/think` 被明确拒绝时退回 `/speak` 说 “The work is done.” | MIT；Python；创建于 2026-08-16，最近 push 2026-11-03；**只认证 macOS Apple Silicon**，README 没提 Windows；完成回报部分自称 “experimental prototype” | 借鉴：(1) 每个 agent 一个 bearer，跟 Agent ID 绑定；(2) 工具立即返回，完成后用 `/think` 回报；(3) 权限请求通过语音转达。不直接跑：我们要的是云协调器加 Windows，而它是 ngrok 把本机暴露出去 | 参考（重点） | README；ARCHITECTURE.md（raw）；GitHub API |
| recipe-agent-delegation | https://github.com/AgoraIO-Conversational-AI/recipe-agent-delegation | GPT Live 负责实时语音，另一个 Responses 模型去推理并通过 MCP 调慢工具，语音不阻塞 | MIT；最近 push 2026-09-25；Next.js；需要启用预览特性 `live-models` | 只作“慢工具不阻塞语音”的思路参考 | 参考 | README |
| recipe-agent-voice-todo | https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-todo | 语音操作看板：FastMCP 挂 `/mcp` 提供 4 个工具，网页每秒轮询 `GET /api/board` 刷新 | MIT；最近 push 2026-08-17 | 参考“工具改状态 → 网页轮询显示进度”的做法 | 参考 | README |
| agent-quickstart-python | https://github.com/AgoraIO-Conversational-AI/agent-quickstart-python | 官方最小骨架：FastAPI（`/get_config`、`/startAgent`、`/stopAgent`）+ Next.js 16 | MIT；最近 push 2026-11-04 | recipe-agent-mcp 已覆盖它的功能；需要干净骨架时再用 | 参考 | README；GitHub API（组织仓库列表） |
| AgoraIO-Community/conversational-ai-nextjs-client | https://github.com/AgoraIO-Community/conversational-ai-nextjs-client | 较早的 Next.js 客户端，用 `/api/invite-agent` 调 v2 REST | MIT；最近 push 2025-12-29；TypeScript；环境变量全部用 `NEXT_PUBLIC_` 前缀，包括 App Certificate 和 Customer Secret，这些会暴露给浏览器 | 有更新的官方 recipe 可用，而且这种密钥暴露不可接受 | 不用 | README；GitHub API |
| AgoraIO-Community/Conversational-AI-Server-Sample | https://github.com/AgoraIO-Community/Conversational-AI-Server-Sample | 实际内容是 Custom LLM 示例（Python / Node.js / Go，GitHub 标记为 Go），不是启动 agent 的后端 | MIT；最近 push 2025-04-02 | 已过时 | 不用 | README；GitHub API 搜索结果 |
| Agora Voice AI Recipes 目录 | https://recipes.agora.io/recipes | 122 个 recipe 的目录；源码仓库 https://github.com/AgoraIO-Community/agora-recipes | agora-recipes 最近提交 2026-11-17；**https://agora-recipes.vercel.app/recipes 返回 404** | 找样例用；和我们相关的有 MCP Tools、Tool Calling、Delegated Reasoning、Push-to-Talk、M5 StickS3 Voice Agent | 参考 | 同左 |

## 问题 3：Agora 在 ESP32 上的方案

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / 平台） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| AgoraIO-Conversational-AI/esp32-client | https://github.com/AgoraIO-Conversational-AI/esp32-client | ESP32-S3 设备用 Agora RTC 推拉音频。设备自己 `POST /projects/{appid}/agents/join` 启动 agent，用编译进固件的 API key/secret 做 HTTP Basic Auth | MIT（README 注明各子项目可能有自己的许可证）；最近提交 2026-04-20；C；板子为 XIAO ESP32-S3 + reSpeaker XVF3800（AIC3104）和 ESP32-S3-Korvo-2 V3（ES8311）；**ESP-IDF v5.2.3 + ESP-ADF v2.7 + FreeRTOS 补丁**；`idf.py set-target esp32s3`；Agora 库需另外下载 `https://rte-store.s3.amazonaws.com/agora_iot_sdk.tar` | **跑不了 Mosaico**：预编译库只有 Xtensa 版本（见 4.4）。只有赛前手里有 ESP32-S3 板子时才有用 | 不用（对 Mosaico）/ 参考 | README、`esp32-korvo-v3/README.md`、`esp32-respeaker` 目录页；ELF 自查 |
| Agora IoT SDK（RTSA）官方支持平台 | https://docs.agora.io/en/realtime-media/iot/reference/supported-platforms | 官方列出的平台只有 Linux（x86_64 / ARM / MIPS 工具链）、HarmonyOS（armv7a）、LiteOS；其他平台用 AOSL 自己移植，页面原话是 “AOSL doesn't automatically add support for every chipset or operating system” | 官方页面没有 ESP32、Xtensa、RISC-V | 证明 Agora 没有公开的 ESP32-S31 支持 | 参考 | 同左；https://www.agora.io/en/products/iot-sdk/ |
| TEN-framework/ten-framework `ai_agents/esp32-client` | https://github.com/TEN-framework/ten-framework/tree/main/ai_agents/esp32-client | 板子是 ESP32-S3-Korvo-V3 和 reSpeaker XVF3800。设备连自建的 TEN-Agent 服务器（`TENAI_AGENT_URL`，通常是 8080 端口）；也要下载同一个 `agora_iot_sdk.tar` | Apache 2.0 “with additional restrictions”；仓库最近提交 2026-11-17；默认 IDF v5.2.3 | 和上面一样受 Xtensa 库限制 | 不用 | `ESP32-S3-Korvo-V3/README.md`；仓库 README；LICENSE |
| AgoraIO-Community/agora-esp32-devkit | https://github.com/AgoraIO-Community/agora-esp32-devkit | 运行 agent-studio-device-firmware 语音运行时，捆绑 Agora RTSA 和 AOSL；设备连托管的 `botstation.agora.io/api` | 项目代码 Apache-2.0，RTSA 单独授权；最近提交 2026-10-30；**ESP-IDF v6.1 基线**；72 个板型，全部是 ESP32-S3 | 是 Agora 在 IDF 6.x 上的最新设备固件，但没有 S31 的证据 | 参考 | README；`components/mybot_stack/README.md` |
| M5 StickS3 Voice Agent（社区 recipe） | https://github.com/Ocean-lhy/RTE2026-StickS3-Demo | ESP-IDF 写的 StickS3 语音 agent，用 Agora RTSA + ConvoAI，控制服务是局域网里的 FastAPI | 2026-10-27 合并进 agora-recipes 的 staging（PR #75）；最近提交 2026-10-26 | 只能参考“设备 → 自建后端 → join”的流程 | 参考 | https://github.com/AgoraIO-Community/agora-recipes/pull/75 |

## 问题 4：ESP-Mosaico 与 ESP-Claw

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / 平台） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| ESP-Mosaico 用户指南（V1.2） | https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s31/esp-mosaico/user_guide.html | 硬件说明：ESP32-S31（NRV16），480×480 触屏，ES8311 编解码，单麦克风，扬声器，IMU，AI 按键（GPIO7），振动马达（GPIO8），65 mAh 电池 | 官方文档 | 当天按这份文档刷机：Type-C 口是 USB 2.0 HS OTG，裸片只能在下载模式下通过它下载固件 | 直接用 | 同左 |
| esp-mosaico-bsp | https://github.com/esp-mosaico/esp-mosaico-bsp | 板级支持包和 24 个示例，包括 `voice_wake_cmd`（WakeNet9 加中文 MultiNet7，默认唤醒词 “Hi,乐鑫”，不联网）、`audio_loopback`、`voice_tts`、`hmi_demo`、`low_power_wakeup`、`usb_extend_screen` 等 | Apache-2.0；最近提交 2026-11-11；C；**要求 “ESP-IDF 6.2 or newer with ESP32-S31 target support”** | **当天固件的起点**：按 AI 键或唤醒词触发，经 Wi-Fi 用 WSS/HTTPS 告诉协调器“开始”。屏幕和振动用来显示状态。USB HID 唤醒棒的可行性也以这里的 `usb_extend_screen` 为证 | 直接用 | README（raw）；`examples/voice_wake_cmd/README.md`；`examples/usb_extend_screen/README.md` |
| esp-mosaico-claw | https://github.com/esp-mosaico/esp-mosaico-claw | 出厂固件源码。基于 ESP-Claw（git 子模块），README 原话：“Integrates the ESP-Claw Agent Runtime with conversations, memory, skills, Lua extensions, and MCP client/server support”。ASR 组件 `asr_service` 只有一个 provider：阿里 DashScope `fun-asr-realtime`（`wss://dashscope.aliyuncs.com/...`，默认语言提示 `zh`）；还有 `wechat_binding_service`、`trial_provider` 等组件 | Apache-2.0；最近提交 2026-11-17；需要 “ESP-IDF 6.x environment with ESP32-S31 support” | 设备自带的 agent 是**另一套语音栈**（云端 ASR 加设备自己配置的 LLM），和 Agora 不相干。想让它调我们的协调器，最现实的是 `http_request` 工具，而不是 MCP（见 4.2） | 参考 | README；`components/asr_service/include/asr_service.h`；`asr_service/idf_component.yml` |
| ESP-Claw | https://github.com/espressif/esp-claw | Espressif 的 “Chat Coding” 设备端 agent 框架，用 C 写成：LLM 接口兼容 OpenAI 和 Anthropic 风格，IM 支持 Telegram、QQ、飞书、微信，另有 Lua、记忆、技能，以及 MCP 的 Server 和 Client | Apache-2.0；最近提交 2026-11-12；支持芯片 ESP32-S3、P4、C5、S31；至少要 8 MB Flash + 8 MB PSRAM | 见 4.2 | 参考 | README（raw）；https://esp-claw.com/en/tutorial/supported-list/；https://esp-claw.com/en/reference-cap/cap-mcp/ |
| esp-mosaico-vibe | https://github.com/esp-mosaico/esp-mosaico-vibe | 给 AI 编码 agent（Codex、Claude Code、Cursor）用的 Mosaico 开发工作区，入口是 `mosaico.py` CLI，配好了 ESP Pilot 和 ESP Component Registry 两个 MCP | 许可证页面没写；最近提交 2026-11-03；Python；固件构建**锁定 ESP-IDF `master` 提交 `7b9cc1ac79f865983f59bb8ff3ff43eb74ff1dbe`** | 当天可以让 Claude Code 借它快速搭 IDF 环境、生成 Mosaico 应用 | 参考（当天可能直接用） | README（raw） |
| esp-mosaico-utils | https://github.com/esp-mosaico/esp-mosaico-utils | ESP-Iris（Developer Gateway 和 Web Workbench）、`mosaico-tools` 主机 CLI、Recovery 固件 | 许可证见 LICENSES.md（未读）；最近提交 2026-11-11；Python | 刷坏后恢复，例如 `mosaico.py recover` | 参考 | README |
| esp-mosaico-matter | https://github.com/esp-mosaico/esp-mosaico-matter | Matter hub 和 bridge 应用 | 最近提交 2026-11-18；C | 和本项目无关 | 不用 | 组织页 https://github.com/esp-mosaico |
| ESP32-S31 USB Device（esp-usb 文档） | https://docs.espressif.com/projects/esp-usb/en/latest/esp32s31/usb_device.html | 基于 TinyUSB 的 USB 设备栈，示例有 HID 键盘鼠标（`tusb_hid`）、CDC、MSC、NCM；提供远程唤醒 API `tinyusb_remote_wakeup()` | ESP32-S31 和 P4 默认端口是 `TINYUSB_PORT_HIGH_SPEED_0` | USB 唤醒棒方案的软件基础 | 参考 | 同左 |

## 问题 5：xiaozhi-esp32 生态

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / 平台） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| 78/xiaozhi-esp32 | https://github.com/78/xiaozhi-esp32 | 开源 AI 语音固件，走 WebSocket 或 MQTT+UDP，默认连 xiaozhi.me；有设备端 MCP（JSON-RPC 2.0 的 `tools/list` 和 `tools/call`）和云端 MCP | MIT；最近提交 2026-11-16；约 33.4k stars；需要 ESP-IDF v6.0.1 以上，推荐 `release/v6.1`；README 原话：“ESP32-S31 builds require IDF 6.1 or later”。**`main/Kconfig.projbuild` 有 `BOARD_TYPE_ESP_MOSAICO`（"Espressif ESP-Mosaico"）**，对应目录 `main/boards/espressif/esp-mosaico`，板型 README 说要用 IDF `master` 的指定提交，因为 v6.2 还没发布 | **兜底方案**：如果当天 Agora 在 Mosaico 上跑不起来，Mosaico 可以先刷小智固件当语音入口，再让小智服务端通过 MCP 调协调器。缺点是绕开了赞助商 Agora | 参考（兜底） | README（raw）；`main/Kconfig.projbuild`；`main/CMakeLists.txt`；`main/boards/espressif/esp-mosaico` 目录页；`docs/mcp-usage.md` |
| 78/mcp-calculator（MCP 接入点官方示例） | https://github.com/78/mcp-calculator | `mcp_pipe.py` 作为 **WebSocket 客户端主动连** `MCP_ENDPOINT`（代码里是 `websockets.connect(uri)`），再把本地 stdio MCP 服务器接上去；也能经 `mcp_proxy` 接 sse/http 类型的服务器；断线后指数退避重连，最长 600 s | MIT（README）；最近提交 2026-02-28；Python | 印证了“设备或电脑主动连出去”的模式，和我们的 WSS 架构一致 | 参考 | README；`mcp_pipe.py`（raw） |
| xinnan-tech/xiaozhi-esp32-server | https://github.com/xinnan-tech/xiaozhi-esp32-server | 自建小智后端：Python 语音服务，Java 加 Vue 的管理台，Docker 部署；README 写明支持 “客户端MCP协议、服务端MCP协议、MCP接入点协议” | MIT；最近提交 2026-11-16 | 兜底时可以自建，以免依赖 xiaozhi.me | 参考（兜底） | README；LICENSE |
| Joho6666/xiaozhi-windows-agent | https://github.com/Joho6666/xiaozhi-windows-agent | 社区写的 Windows MCP 桥：经 xiaozhi.me 的 MCP 接入点（WebSocket，URL 里带 token）提供 49 个本地工具，包括调度 Codex CLI 和 Claude Code、读写全盘文件、执行 shell | MIT；只有 4 个提交，最近一次 2026-08-23；Python 3.11+；启动输出里写着 “Permission UNRESTRICTED” | 只参考它“调度本地 Claude Code”的工具设计；安全面太大，不能直接用 | 参考 | README；https://glama.ai/mcp/servers/ay51zoittp（只用来找到仓库地址） |
| shenjingnan/xiaozhi-client | https://github.com/shenjingnan/xiaozhi-client | Node 写的 xiaozhi.me 接入点客户端，能聚合多个 MCP Server | MIT；最近提交 2026-05-01；Node ≥22 | 无 | 不用 | README |

## 问题 6：其他开源语音栈的 ESP32 客户端（只作兜底参考）

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / 平台） | 在本项目怎么用 | 建议 | 来源 |
|---|---|---|---|---|---|---|
| pipecat-ai/pipecat-esp32 | https://github.com/pipecat-ai/pipecat-esp32 | ESP32 通过 SmallWebRTC 连 Pipecat bot（`/api/offer`） | MIT；最近提交 2025-10-06；测试过 esp32s3（S3-BOX-3、M5 CoreS3）和 linux | 不支持 S31，而且不是赞助商 | 不用 | README |
| livekit/client-sdk-esp32 | https://github.com/livekit/client-sdk-esp32 | LiveKit 的 ESP32 SDK：Opus 音频、H.264 视频，可以对 agent 做 RPC | Apache-2.0；最近提交 2026-11-18；“Developer Preview”；只支持 ESP32-S3 和 P4；IDF ≥5.4 | 不支持 S31 | 不用 | README；https://docs.livekit.io/frontends/build/hardware/esp32/ |

---

## 关键事实

### 1(a) Custom tools（HTTP GET/POST）

来源：https://docs.agora.io/en/ai/build/tools/custom-tools ；https://docs.agora.io/en/api-reference/api-ref/conversational-ai/join ；https://docs.agora.io/en/ai/release-notes

- **只支持同步调用**：`execution.mode` 只能是 `sync`。原文是 “Tool calling supports only synchronous `GET` and `POST` requests to a single endpoint per tool.” 不支持的有 “Asynchronous tools, callbacks, polling, or stored/reusable tool references”，以及 PUT/PATCH/DELETE、自动重试、跟随 3xx 重定向（算失败）、OAuth、请求签名、mTLS。
- **不支持 Custom LLM**：原文是 “Custom LLMs and Dify aren't supported.” 适用于支持 function calling 的文本 LLM 和 MLLM；MLLM 用 `mllm.tools`（v2.13，2026-09-25）。
- **超时**：`server.timeout_ms` 默认 10000，范围 1000–100000，也就是最长 100 s。超时、网络错误、响应过大都算失败，不会重试。
- **数量与大小**：
  - 每个 agent 最多给 LLM 暴露 32 个工具。custom、MCP、内置、模型原生工具共用这个名额和同一个命名空间，名字冲突或超限时 agent 启动失败。
  - 参数 schema 序列化后不超过 64 KiB；POST body 不超过 64 KiB。
  - headers 最多 32 条、共 16 KiB；headers 里不能用 `{{args.x}}`。
  - 响应不超过 1 MiB，而且必须是 UTF-8。
  - URL 必须以 `https://` 开头。join 参考页给的上限是 2048；custom-tools 页说渲染后的 URL 上限 8192 字节。
- **命名**：REST 版函数名的正则是 `^[a-zA-Z][a-zA-Z0-9]{0,63}$`，**不能有下划线**，所以要写 `wakeLaptop`，不能写 `wake_laptop`；也不能以 `mcp` 开头。
- **开关**：必须设 `properties.advanced_features.enable_tools=true`，SDK 里对应 `with_tools(True)`。不开的话模型看不到工具，也不会报错。
- **运行时行为**：同一轮的多个工具调用并发执行，引擎等全部结果回来才进入下一轮 LLM。等待期间只播放已配置的 filler words，custom tools 自己不会触发垫话。
- **鉴权**：静态 header 可以引用 `{{template_variables.x}}`，例如 `Authorization: Bearer ...`。
- **公网要求**：REST 文档只写了 “absolute HTTPS URL”。Agent Studio 版文档说 host 不能是 localhost 或私网地址，但那是另一个入口（https://docs.agora.io/en/ai/studio/build/custom-tools ，它支持 GET/POST/PUT/PATCH/DELETE，默认超时 30 s）。recipe-agent-custom-http-tools 的 README 写明 localhost 不行。

### 1(b) MCP tools

来源：https://docs.agora.io/en/ai/build/tools/mcp-tools ；https://docs.agora.io/en/api-reference/api-ref/conversational-ai/join ；https://docs.agora.io/en/ai/release-notes ；https://github.com/AgoraIO-Conversational-AI/recipe-agent-mcp

- **调用方式**：Agora 云端作为 MCP 客户端，主动调用你的 MCP 服务器。`transport` 只有一个取值，原文是 “Currently only `streamable_http` is supported.” 文档没提 SSE。
- **REST 字段**：`properties.llm.mcp_servers[]`，MLLM 用 `properties.mllm.mcp_servers[]`。每项字段如下：
  - `name`：必填，最多 48 个字符，只能是英文字母和数字。
  - `endpoint`：必填，MCP 服务器地址，例如 `https://<coordinator>/mcp`。
  - `transport`：选填，只能是 `streamable_http`。Python SDK 省略时默认就是它（recipe-agent-mcp 的 `mcp_config.py` 注释）。
  - `headers`：选填，原文是 “HTTP header information to include when requesting the MCP server, such as authentication information”，**可以放 `Authorization: Bearer <token>`**。
  - `allowed_tools`：选填。省略或写 `["*"]` 表示全部启用，`[]` 表示一个都不启用。名字对不上时，原文是 “the agent can hang mid-response with no error”，所以建议先用 `tools/list` 核对工具名。
  - `timeout_ms`：选填，超时后 agent 不再等待，继续执行后续逻辑。文档没给取值范围。
- **开关**：同样要 `advanced_features.enable_tools=true`。只挂上 MCP 服务器而不开这个开关时，LLM 永远不会调用工具，也不报错。
- **适用的 agent 类型**：
  - 级联式（ASR + LLM + TTS，放在 `llm` 块）：v2.4（2026-02-02）起支持。
  - MLLM（实时语音模型，放在 `mllm` 块）：v2.12（2026-09-10）起可以通过 REST 使用，v2.13 起 Python、TS、Go SDK 的所有 MLLM vendor 类都支持。
  - MCP 是否支持 Custom LLM：文档没写，见“未能核实”。
- **可达性**：文档前提只写了 “An MCP server reachable over HTTP or HTTPS”。recipe-agent-mcp 和 recipe-agent-voice-todo 的 README 写明 `MCP_ENDPOINT` 必须公网可达、不能是 localhost，因为调用来自 Agora 云端。本项目的协调器本来就在 AWS 上、有 HTTPS 地址，满足这个条件。
- **延迟**：文档提示工具调用会增加延迟，建议配 filler words。

### 1(c) 协调器能否主动推送进度或让 agent 开口

来源：https://docs.agora.io/en/api-reference/api-ref/conversational-ai/speak ；https://docs.agora.io/en/api-reference/api-ref/conversational-ai/think ；https://docs.agora.io/en/ai/release-notes ；https://github.com/AgoraIO-Conversational-AI/recipe-agent-voice-coder

- **能**。可以走服务端 REST，鉴权方式是 `tokenAuth` 或 `basicAuth`，需要知道 `agentId`（join 返回的值）。
  - **`POST https://api.agora.io/api/conversational-ai-agent/v2/projects/{appid}/agents/{agentId}/speak`**：TTS 直接播报，不经过 LLM。字段如下：
    - `text`：必填，**不超过 512 字节**。
    - `priority`：`INTERRUPT`（默认）、`APPEND` 或 `IGNORE`。
    - `interruptable`：默认 true。
    - 限制：**不支持 `mllm` 配置**。
  - **`POST .../agents/{agentId}/think`**：把 `text` 当作用户输入注入，由 LLM 生成回答。可选字段如下：
    - `on_listening_action`：`inject`、`interrupt`、`append`、`ignore`，默认 `interrupt`。
    - `on_thinking_action`：`interrupt`、`append`、`ignore`，默认 `interrupt`。
    - `on_speaking_action`：`interrupt`、`append`、`ignore`，**默认 `ignore`**。agent 正在说话时，默认会丢掉这条指令，建议设成 `append`。
    - `interruptable`：可选。
    - `metadata`：可选。
    - 文档没写 MLLM 限制，也没写长度限制。
  - 其他端点还有 `interrupt` 和 `update`（运行时改配置），见 https://docs.agora.io/en/api-reference/api-ref/conversational-ai 。
- 客户端 toolkit 从 v2.12 起提供 `speak` 和 `think` 方法（Android、iOS、Web，经 RTM），手机网页也能注入。
- **官方先例**：recipe-agent-voice-coder 完成任务后，向 `/think` 发送不超过 8 KiB 的 `LOCAL_WORK_COMPLETED` 信封，`/think` 被明确拒绝时才退回一次 APPEND 方式的 `/speak`。它自己标注这部分是 “experimental prototype”。
- **结论**：Claude Code 生成网页要几分钟，远超工具最长 100 s 的超时，所以：
  1. 协调器工具（例如 `startBuild`）收到请求后立即返回 “accepted, jobId”。
  2. 中间进度用 `/speak` 播报短句。
  3. 完成后用 `/think`（`on_speaking_action=append`）让 LLM 发起语音确认。
  4. 协调器要保存 `agentId`，所以最好由协调器自己调用 join。

### 4. ESP-Mosaico 与 ESP32-S31

**4.1 硬件与形态**
- 来源：https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s31/esp-mosaico/user_guide.html ；https://documentation.espressif.com/esp32-s31_datasheet_en.html
- SoC 是 ESP32-S31NRV16：双核 32 位 RISC-V（RV32IMAFC），最高 320 MHz，16 MB 封装内 PSRAM，2.4 GHz Wi-Fi 6，BT 5.4，802.15.4。数据手册目前是 “PRELIMINARY”（v0.5）。
- 官方文档把它定义为 “expandable smart interaction development kit”（CoreBoard 加 BaseBoard，65 mAh 电池），**没有说它是腕戴设备**。

**4.2 是否自带 agent 运行时，能否当 MCP 客户端调用我们的协调器**
- 来源：https://github.com/esp-mosaico/esp-mosaico-claw ；https://esp-claw.com/en/reference-cap/cap-mcp/ ；https://raw.githubusercontent.com/espressif/esp-claw/master/components/claw_capabilities/cap_mcp_client/src/cap_mcp_client_core.c ；https://components.espressif.com/components/espressif/mcp-c-sdk ；https://esp-claw.com/en/reference-cap/cap-http-request/
- **有**。出厂固件源码是 esp-mosaico-claw，集成了 ESP-Claw Agent Runtime（对话、记忆、技能、Lua、MCP client/server）。
- **MCP 客户端（`cap_mcp_client`）的实际能力有限**：
  - 给 LLM 的工具是 `mcp_list_tools`、`mcp_call_tool`（参数 `server_url`、`tool_name`，可选 `endpoint`）和 `mcp_discover`（发现局域网服务器）。
  - **默认对 LLM 不可见**，原文是 “No (requires Skill activation)”。
  - 底层用 `espressif/mcp-c-sdk ^2.0.0` 的 HTTP 客户端传输，即 JSON-RPC over HTTP POST，默认协议版本 2025-11-25；对 streamable HTTP 的支持是 “POST is supported; GET is currently 405 when SSE is not enabled”。
  - 源码里的 `esp_http_client_config_t` 只设置了 url、timeout（20000 ms）、buffer 和 keep-alive。**没有任何 `esp_http_client_set_header` 调用，所以没法带 `Authorization` 头**；也没看到证书或 `esp_crt_bundle` 的配置。
  - 每次调用都会新建 MCP 会话、做一次初始化。
- **MCP 服务器（`cap_mcp_server`）**：走 SSE 传输，用 mDNS 在局域网广播。
- **更现实的路径**：ESP-Claw 的 `http_request` 工具默认对 LLM 可见，支持 GET、POST 等方法和自定义 headers，可以访问 HTTP/HTTPS。但**必须配置 `http_allowlist`**，否则所有请求都会被拒绝；超时默认 15 s，范围 1–120000 ms。
- **另一个关键点**：这个设备端 agent 的 ASR 是阿里 DashScope `fun-asr-realtime`（默认 `zh`），LLM 由设备自己配置。它是独立于 Agora 的另一条语音链路。

**4.3 ESP-IDF 版本**
- 来源：https://raw.githubusercontent.com/esp-mosaico/esp-mosaico-bsp/master/README.md ；https://github.com/espressif/esp-idf/releases ；https://developer.espressif.com/hardware/esp32s31/ ；https://raw.githubusercontent.com/esp-mosaico/esp-mosaico-vibe/main/README.md ；https://github.com/78/xiaozhi-esp32/tree/main/main/boards/espressif/esp-mosaico
- BSP 原文要求 “ESP-IDF 6.2 or newer with ESP32-S31 target support”，并提示可能要用 `idf.py --preview set-target esp32s31`。
- 截至 2026-11-18，esp-idf 最新正式版是 **v6.1.1**（11 月 16 日）。v6.1 的发布说明写的是 “Added preview support for ESP32-S31”。Espressif 开发者站的原话是 “please update to the HEAD of master branch to develop with ESP32-S31 chips”。
- 实际上大家用的都是 master：
  - esp-mosaico-vibe 锁定 master 提交 `7b9cc1ac79f865983f59bb8ff3ff43eb74ff1dbe`。
  - xiaozhi 的 esp-mosaico 板型 README 也写着要用 master 的指定提交，因为 v6.2 还没发布。
- 例外：BSP 里 `voice_wake_cmd` 的 README 写的是 “ESP-IDF 5.5 or later”，和顶层 README 矛盾，**以顶层 6.2 和 master 为准**。

**4.4 Agora 的 ESP32 SDK 能否跑在 S31 上（自行核验）**
- 来源：https://rte-store.s3.amazonaws.com/agora_iot_sdk.tar （Last-Modified 2025-01-26，10,075,136 字节）；https://raw.githubusercontent.com/bminor/glibc/master/elf/elf.h
- 解包后的 `CMakeLists.txt` 用 `add_prebuilt_library` 引入了 `libs/librtsa.a`、`libahpl.a` 和 `libagora-cjson.a`。
- 逐个读取 ELF 头：`librtsa.a` 里 111 个、`libahpl.a` 里 46 个 ELF 目标文件，`e_machine` 全是 **94，也就是 `EM_XTENSA`**（glibc `elf.h`：`#define EM_XTENSA 94`；RISC-V 是 243）。
- **结论：这些预编译库只能链接到 Xtensa 芯片（ESP32-S3 这一类），不能用于 RISC-V 的 ESP32-S31。** esp32-client 和 TEN esp32-client 都依赖这个包。
- 要移植的话：
  - 需要 Agora 提供 RISC-V（esp32s31）版的 RTSA、ahpl 和 AOSL 闭源库。
  - 要从 IDF 5.2.3 加 ESP-ADF 2.7 迁到 IDF 6.x master。
  - 音频改用 Mosaico BSP 的 ES8311 路径。
- 比赛前完成移植不现实，除非 Agora 现场提供 S31 版本的库。

**4.5 ESP32-S31 能否做原生 USB OTG 和 USB HID 设备**
- 来源：数据手册；Mosaico 用户指南；https://docs.espressif.com/projects/esp-usb/en/latest/esp32s31/usb_device.html ；https://raw.githubusercontent.com/esp-mosaico/esp-mosaico-bsp/master/examples/usb_extend_screen/README.md
- **能**。数据手册列有 “USB 2.0 High-Speed OTG” 和独立的 “USB Serial/JTAG controller”。Mosaico 的 Type-C 口就是这个 HS OTG 口。
- esp-usb 文档有 ESP32-S31 的设备栈：基于 TinyUSB，有 HID 键盘鼠标示例，提供 `tinyusb_remote_wakeup()`。原文要求 “Call this function only while the device is suspended and the host has enabled remote wakeup”。
- BSP 的 `usb_extend_screen` 示例在 Windows 10/11 上实现了显示（vendor 类）、HID 触摸和 UAC 的复合设备（`USB\VID_303A&PID_2986`）。原文是 “This application owns TinyUSB”，而且它默认关掉了 BSP 的 USB CDC 控制台，刷机和看日志改走 UART。**也就是说，做 HID 唤醒棒会占用这个 Type-C 口的控制台。**

---

## 未能核实

- Agora MCP tools 能否和 `llm.vendor=custom`（Custom LLM）一起用：MCP 文档没写。custom tools 明确不支持 Custom LLM。
- Agora MCP 的 `timeout_ms` 取值范围和上限、MCP 服务器数量上限（只知道全部工具合计 32 个）、Agora 实现的是哪个 MCP 协议版本、是否缓存 `tools/list`。
- MCP 端点是否“必须 HTTPS”：官方文档只写了 “HTTP or HTTPS”，“必须公网”出自 recipe 的 README。另外，Agora 云端调用工具时的出口 IP 是否固定（能否加白名单）也没查到。
- `/think` 在 MLLM 模式下能不能用、`text` 有没有长度上限、频率限制多少，文档都没写。
- recipe-agent-voice-coder 里传给 Agora 的具体 `mcp_servers.headers` 字段格式：ARCHITECTURE.md 只说了 “bearer header”，没有读源码确认。
- Agora 有没有 RISC-V 或 ESP32-S31 版本的 RTSA / IoT SDK，比赛现场会不会提供；`agora_iot_sdk.tar` 的许可条款（包里没有许可证文件，README 也没说）。
- ESP-Claw MCP 客户端访问 `https://` 服务器时证书校验能否通过；mcp-c-sdk 客户端有没有别的途径设置 Authorization 头。
- Mosaico 出厂固件的默认行为：AI 键默认做什么、是否支持英文 ASR、`trial_provider` 用的是哪家 LLM 或试用额度。这些组件源码没有读。
- “ESP-Mosaico 腕戴设备”这个说法：官方文档没有腕戴或表带的描述，可能是比赛方另行提供的外壳。
- 用 ESP32-S31 的 USB HID 远程唤醒，能否把处于 Modern Standby 或 S3 睡眠的 Windows 笔记本叫醒：没有实测资料，这取决于笔记本固件和 Windows 的电源设置。
- xiaozhi.me MCP 接入点的确切 URL 格式、token 规则和工具数量限制：只从 `mcp_pipe.py` 看出“出站 WebSocket”，没有读 xiaozhi.me 控制台的官方文档。
- xiaozhi-esp32 的 esp-mosaico 板型实际启用了哪些功能（唤醒词、显示、摄像头），`config.json` 没有读。
- ESP-IDF v6.2 什么时候发布。
- esp-mosaico-vibe、esp-mosaico-utils、esp-mosaico-matter 的许可证：页面没显示，vibe 和 matter 的 `LICENSE` 返回 404。
- https://agora-recipes.vercel.app/recipes 返回 404，目录以 https://recipes.agora.io/recipes 为准。
