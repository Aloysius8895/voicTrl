# 03 · Agent 编排、跨设备协议、长期记忆与参考产品（调研）

- 调研日期：2026-11-18（距 11/28 演示还有 10 天）
- 方法：只采信一手来源（官方规范与文档、GitHub 仓库 README 与源码、PyPI / GitHub REST API 元数据），每条结论后附来源 URL。
- "最近活动"取 GitHub REST API `https://api.github.com/repos/<owner>/<repo>` 的 `pushed_at`，"版本"取 PyPI JSON API `https://pypi.org/pypi/<pkg>/json`，均在 2026-11-18 查询。
- 一手来源里查不到的内容统一列在文末"未能核实"，正文不做推测。

---

## 对本项目最有用的 6 个

1. **MCP 官方 Python SDK（`mcp` 2.x，`MCPServer`，即原 FastMCP）**：同一套工具可以用 `streamable_http_app()` 挂进现有 FastAPI。同一个端点会自动同时服务 2026-07-28 新协议的客户端和旧的 `initialize` 握手客户端，而 Agora、Claude Code、ESP-Claw 都是 MCP 客户端。（[legacy-clients](https://py.sdk.modelcontextprotocol.io/run/legacy-clients/)，[asgi](https://py.sdk.modelcontextprotocol.io/run/asgi/)）
2. **Agora ConvoAI 的工具接入方式和 `speak` API**：它决定了工具该怎么设计。MCP 只支持 `streamable_http`；自定义 HTTP 工具只能是同步 GET/POST，超时 1–100 s，不支持异步、回调或轮询。所以长任务必须"先立即返回 task_id，再由 coordinator 用 `speak`（≤512 字节，可以 APPEND）播报进度和结果"。（[MCP tools](https://docs.agora.io/en/ai/build/tools/mcp-tools)，[custom tools 源文件](https://github.com/AgoraIO/docs-portal/blob/main/content/docs/en/ai/build/tools/custom-tools.mdx)，[speak](https://docs.agora.io/en/api-reference/api-ref/conversational-ai/speak)）
3. **Claude Code headless（`claude -p --output-format stream-json`）和 Claude Agent SDK**：充当 B 机上的"智能子 agent"。流式 JSON 事件可以直接转成进度上报。SDK 还提供 hooks、subagents 和进程内 MCP 工具，Python 包自带 Claude Code CLI。（[headless](https://code.claude.com/docs/en/headless)，[Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)，[SDK README](https://github.com/anthropics/claude-agent-sdk-python)）
4. **OpenClaw**：和本项目长期形态最接近的开源产品。它有 Gateway 加配对 node 的结构（WebSocket、两层审批、`node.invoke`），能把 Claude Code 当执行后端，能在配对设备上跑会话，记忆是用户可直接编辑的 Markdown 文件，还有原生 Windows Hub。长期首选参考，也可以考虑当底座。（[README](https://github.com/openclaw/openclaw)，[nodes](https://docs.openclaw.ai/nodes)）
5. **A2A v1.0 规范**：演示不接入，但它的 Task 模型适合直接拿来当我们自定义 WSS 协议的消息结构，包括状态集合 SUBMITTED/WORKING/INPUT_REQUIRED/AUTH_REQUIRED/COMPLETED/FAILED/CANCELED/REJECTED、状态和产物的流式事件，以及 webhook push。这样日后再对外暴露 A2A，代价最小。（[spec](https://a2a-protocol.org/latest/specification/)）
6. **自建 SQLite（+FTS5）记忆表，长期再接 mem0 OSS**：自建表最轻，用户可以完整地查看、编辑、删除。mem0 OSS 提供 `add/search/get_all/get/update/delete/delete_all`，还有自托管 dashboard，可以做第二阶段的抽取和语义检索层。Omi 的"记忆分类，可在 App 里审阅、编辑、删除"是 UX 参考。（[mem0 llms.txt](https://docs.mem0.ai/llms.txt)，[Omi 记忆](https://docs.omi.me/doc/how-omi-works/conversations-and-memories)，[FTS5](https://www.sqlite.org/fts5.html)）

## 建议（演示 vs 长期）

1. **演示**：FastAPI + SQLite 的 coordinator 用 `MCPServer` 暴露十个以内的工具（`stateless_http=True`，用 Bearer 头鉴权）。Agora 通过 `llm.mcp_servers` 接入，Claude Code 用 `claude mcp add --transport http` 接同一个端点。MCP 联调不顺时，退回 Agora 自定义 HTTP 工具，背后还是同一组 FastAPI 路由。
2. **演示**：coordinator 和设备之间用自定义的 JSON-over-WSS，由设备主动外连，消息字段照搬 A2A Task（task_id/state/message/artifact）。编排用 SQLite 里的显式状态机加固定模板，不引入 LangGraph、A2A、OpenClaw、UFO。
3. **演示**：B 机 daemon 调 `claude -p --output-format stream-json`（或 Claude Agent SDK）并转发事件。所有长工具一律先返回 task_id；进度和完成通过 Agora `speak`（APPEND）播报；"用户确认"在状态机里做成一个等待态。
4. **长期**：MCP 继续作为面向所有 LLM 宿主的统一工具面（Agora、Claude、ESP-Claw，以及与 Home Assistant 互通）。需要可恢复的人工中断和动态分支时，再上 LangGraph（SqliteSaver/PostgresSaver）。设备侧逐步换成 Claude Agent SDK（用 hooks 上报进度，用进程内工具）。要和第三方 agent 互通时，在 coordinator 上加 A2A 服务端。
5. **长期**：记忆以自有 SQL 表作为"用户可见的真相源"（可审计、可删除），mem0 OSS 只做抽取和检索层。多设备节点的配对审批、命令面审批和 Markdown 记忆参考 OpenClaw，DAG 式多设备规划参考 UFO³ Galaxy。

---

## 分类对比表

### A. 协议：coordinator↔工具、agent↔agent

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议（11/28 演示 / 长期） | 来源 |
|---|---|---|---|---|---|---|
| MCP 规范（当前版 2026-07-28） | https://modelcontextprotocol.io/specification/latest | LLM 宿主与工具/数据之间的 JSON-RPC 协议。本版改成逐请求携带元数据、无状态；Streamable HTTP 去掉了会话和 GET 流；长任务移到 Tasks 扩展 | 规范仓库许可证在 GitHub API 中显示 NOASSERTION；2026-11-18 有推送；与 OS 无关 | coordinator 作为 MCP server，给 Agora、Claude Code、ESP-Claw 暴露工具 | 演示：用 / 长期：用（统一工具面） | [spec](https://modelcontextprotocol.io/specification/latest)，[transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)，[streamable-http](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) |
| MCP Python SDK `mcp`（`MCPServer`） | https://github.com/modelcontextprotocol/python-sdk | 官方 SDK。v2 把 `FastMCP` 改名为 `MCPServer`；`streamable_http_app()` 可挂进 FastAPI；同一端点服务新旧两代客户端；用 `ctx.report_progress` 报进度；用 `TokenVerifier` + `AuthSettings` 做 OAuth 资源服务器 | MIT / PyPI 2.3.0（2026-10-02），仓库 2026-11-17 推送 / README 写 Python 3.11+，PyPI 未声明 OS 限制 | 内嵌在 coordinator 的 FastAPI 中 | 演示：用 / 长期：用 | [README](https://github.com/modelcontextprotocol/python-sdk)，[whats-new](https://py.sdk.modelcontextprotocol.io/whats-new/)，[asgi](https://py.sdk.modelcontextprotocol.io/run/asgi/)，[legacy-clients](https://py.sdk.modelcontextprotocol.io/run/legacy-clients/)，[progress](https://py.sdk.modelcontextprotocol.io/handlers/progress/)，[authorization](https://py.sdk.modelcontextprotocol.io/run/authorization/) |
| MCP Tasks 扩展 | https://modelcontextprotocol.io/extensions/tasks/overview | 长任务先返回 `taskId`，客户端用 `tasks/get` 轮询，用 `tasks/update` 补充输入，用 `tasks/cancel` 取消；状态有 working/input_required/completed/failed/cancelled | 官方扩展，需要客户端和服务端都 opt-in；Python SDK v2 明确"does not implement yet" | 语义上最贴近"长任务 + 进度"，但 SDK 没实现，主流客户端是否支持也无法证实 | 演示：不用 / 长期：观察 | [tasks](https://modelcontextprotocol.io/extensions/tasks/overview)，[whats-new](https://py.sdk.modelcontextprotocol.io/whats-new/) |
| A2A 协议 v1.0 | https://github.com/a2aproject/A2A | agent↔agent 协议：Agent Card 发现、Task 生命周期、SSE 流、webhook push 通知；绑定有 JSON-RPC、gRPC、HTTP+JSON，也允许自定义绑定 | Apache-2.0，Linux Foundation 项目 / v1.0.0 发布于 2026-03-12，v1.0.1 发布于 2026-05-28，仓库 2026-11-18 推送 / 与 OS 无关 | 借它的 Task 状态和事件模型设计 WSS 消息；长期用于对外互通 | 演示：参考 / 长期：可选接入 | [README](https://github.com/a2aproject/A2A)，[spec](https://a2a-protocol.org/latest/specification/)，[releases](https://github.com/a2aproject/A2A/releases) |
| a2a-python（`a2a-sdk`） | https://github.com/a2aproject/a2a-python | A2A 官方 Python SDK：实现 1.0，兼容 0.3；JSON-RPC、REST、gRPC 的客户端和服务端都有；核心是 `AgentExecutor`（`execute`/`cancel`）、`EventQueue`、`TaskUpdater`；extras 包括 `fastapi`、`sqlite` | Apache-2.0 / 1.3.1（2026-11-17）/ Python 3.10+，PyPI 标 OS Independent | 长期在 coordinator 上提供 A2A 服务端 | 演示：跳过 / 长期：可用 | [README](https://github.com/a2aproject/a2a-python)，[tutorial](https://a2a-protocol.org/latest/tutorials/python/4-agent-executor/)，[PyPI](https://pypi.org/project/a2a-sdk/) |
| Agora ConvoAI 工具接入（MCP tools / custom tools / speak） | https://docs.agora.io/en/ai/build/tools/mcp-tools | MCP：配置 `llm.mcp_servers`（name/endpoint/transport=`streamable_http`/headers/allowed_tools/timeout_ms），并打开 `advanced_features.enable_tools`。custom：只能同步 GET/POST，`timeout_ms` 1000–100000（默认 10000），不支持异步、回调、轮询。所有工具共享一个命名空间，最多 32 个。`speak`：≤512 字节，优先级 INTERRUPT/APPEND/IGNORE，MLLM 配置下不可用 | Agora 托管服务 | 语音入口调用 coordinator 的工具；进度和结果靠 `speak` 回播 | 演示：用 / 长期：用 | [mcp-tools](https://docs.agora.io/en/ai/build/tools/mcp-tools)，[custom-tools 源文件](https://github.com/AgoraIO/docs-portal/blob/main/content/docs/en/ai/build/tools/custom-tools.mdx)，[speak](https://docs.agora.io/en/api-reference/api-ref/conversational-ai/speak) |
| ESP-Claw MCP 能力（esp-mosaico-claw 继承） | https://esp-claw.com/en/reference-cap/cap-mcp/ | `cap_mcp_client`：设备上的 LLM 可调用 `mcp_list_tools`、`mcp_call_tool`、`mcp_discover`（参数为 `server_url` + `endpoint`）。`cap_mcp_server`：把设备能力暴露成 MCP server，SSE 传输，mDNS 广播 | Apache-2.0 / esp-claw 2026-11-12 推送，esp-mosaico-claw 2026-11-17 推送 / 固件（ESP32-S31，ESP-IDF 6.x） | ESP-Mosaico 板子可以直接调 coordinator 的 MCP 工具，但有鉴权缺口，见"关键事实 1.5" | 演示：可选（要展示 ESP-Mosaico 时用）/ 长期：用 | [esp-mosaico-claw README](https://github.com/esp-mosaico/esp-mosaico-claw)，[cap-mcp](https://esp-claw.com/en/reference-cap/cap-mcp/)，[client 源码](https://github.com/espressif/esp-claw/blob/master/components/claw_capabilities/cap_mcp_client/src/cap_mcp_client_core.c)，[mcp-c-sdk](https://components.espressif.com/components/espressif/mcp-c-sdk/versions/2.0.0/readme) |

### B. 跨设备 / 多设备 Agent 项目

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议（11/28 演示 / 长期） | 来源 |
|---|---|---|---|---|---|---|
| OpenClaw | https://github.com/openclaw/openclaw | 个人 AI 助手。Gateway 是控制平面；node（macOS/iOS/watchOS/Android/无头主机）通过 WebSocket 接入，暴露 `camera.*`、`device.*`、`notifications.*`、`system.*` 等命令；有 skills/ClawHub、Markdown 记忆，可以用 Claude Code 当 CLI 后端，可以在配对设备上跑"Cloud Sessions" | MIT / 2026-11-18 推送，文档发布日志最新为 v2026.11.5 / 支持：有原生 Windows Hub（Win10 20H2+、Win11），带 Windows node 模式；安装器支持 PowerShell；需要 Node 24.16+ 或 26.1+ | 参考它的配对、审批和命令面设计，以及记忆文件结构 | 演示：参考（不引入，学习成本和安全面都太大）/ 长期：首要参考或底座候选 | [README](https://github.com/openclaw/openclaw)，[nodes](https://docs.openclaw.ai/nodes)，[windows](https://docs.openclaw.ai/platforms/windows)，[llms.txt](https://docs.openclaw.ai/llms.txt) |
| microsoft/UFO（UFO³ Galaxy + UFO²） | https://github.com/microsoft/UFO | UFO² 是 Windows 桌面 GUI agent。Galaxy 做多设备编排：ConstellationAgent 把任务拆成 DAG（TaskConstellation），按设备能力分派；设备之间用基于 WebSocket 的 AIP 协议；设备 agent 集成 MCP | MIT / 2026-10-30 推送；Releases 页最新 v3.0.10（页面未显示年份）/ UFO² 只支持 Windows；Galaxy 设备支持 Windows、Linux、Android | 参考 DAG 规划和"按能力选设备"的思路 | 演示：跳过 / 长期：参考 | [README](https://github.com/microsoft/UFO)，[galaxy README](https://github.com/microsoft/UFO/blob/main/galaxy/README.md)，[quick start](https://microsoft.github.io/UFO/getting_started/quick_start_galaxy/)，[releases](https://github.com/microsoft/UFO/releases) |
| Open Interpreter 01 | https://github.com/OpenInterpreter/01 | 开源语音界面平台：有 Light Server（面向 ESP32）、LiveKit Server，客户端覆盖 Android/iOS/ESP32 | AGPL-3.0 / 最后推送 2024-11-01（两年没动）；README 自称"experimental ... lacks basic safeguards" / Windows 未核实 | 无 | 演示：跳过 / 长期：跳过（AGPL 且停更） | [README](https://github.com/OpenInterpreter/01)，GitHub API |
| BasedHardware/omi | https://github.com/BasedHardware/omi | 可穿戴项链 + 手机/桌面 App + 后端，把对话转成可检索、可对话的记忆；提供 Developer API、MCP server、CLI | MIT（托管的 Omi Cloud 和付费计划另外说明）/ 2026-11-18 推送 / 有 Windows 桌面 App（`desktop/windows` 源码运行） | 记忆 UX 和数据模型（分类、溯源到对话）作参考 | 演示：跳过 / 长期：参考（后端依赖 Firebase，自托管成本高） | [README](https://github.com/BasedHardware/omi)，[记忆模型](https://docs.omi.me/doc/how-omi-works/conversations-and-memories) |
| trycua/cua | https://github.com/trycua/cua | Computer-use 基础设施：Cua Driver 通过 CLI、MCP 或 SDK 操作 macOS/Windows/Linux 原生应用；Lume 管理 Apple Silicon 虚拟机；Cua Spaces 管理 agent 桌面；Sandbox SDK | MIT / 2026-11-18 推送 / Cua Driver 支持 Windows（PowerShell 安装）；Cua Spaces App 要求 macOS 26+ | 将来要让 agent 操作没有 API 的桌面 GUI 时可用（例如电视、旧应用） | 演示：跳过 / 长期：备选 | [README](https://github.com/trycua/cua) |
| Letta Code 远程环境（跨设备参考） | https://docs.letta.com/platform/computers/byom | `letta server --env-name` 让机器**主动外连** WebSocket 到 Letta Cloud，成为可选执行环境；agent 的记忆留在云端，工具在选中的机器上执行 | letta-code 为 Apache-2.0 / 需要登录 Letta Cloud / wheels 支持 Windows x64 | 印证了"设备外连 WSS、记忆在云端"的架构（与我们已定方案相同） | 演示：参考 / 长期：参考 | [byom](https://docs.letta.com/platform/computers/byom)，[letta-code README](https://github.com/letta-ai/letta-code) |

### C. 编排框架

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议（11/28 演示 / 长期） | 来源 |
|---|---|---|---|---|---|---|
| 显式状态机（自写，SQLite `tasks` 表） | —（自建） | 固定模板：`wake_A → wake_B → send_prompt → B_running → open_on_target → await_confirm → done/failed`；每次状态变化落库，WSS 事件驱动 | — | coordinator 核心 | 演示：**用** / 长期：作为基线保留 | 设计建议（非外部事实） |
| LangGraph | https://github.com/langchain-ai/langgraph | 低层编排运行时：图状态机；checkpointer 每个 super-step 存一次快照；`interrupt()` 暂停后用 `Command(resume=...)` 恢复（被中断的节点会**从头重跑**）；出错后用 `graph.invoke(None, config)` 续跑；节点级 pending writes 容错 | MIT / PyPI 1.2.22（2026-11-14），仓库 2026-11-18 推送 / PyPI 未声明 OS 限制 | 工作流变成动态的、需要可恢复的人工确认时，替换手写状态机 | 演示：不用 / 长期：候选 | [overview](https://docs.langchain.com/oss/python/langgraph/overview)，[checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)，[interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) |
| Claude Agent SDK（Python） | https://github.com/anthropics/claude-agent-sdk-python | 把 Claude Code 封装成库：内置工具、hooks（`PreToolUse`/`PostToolUse`/`SubagentStop`/`Notification` 等）、subagents（`AgentDefinition`，默认在后台运行）、MCP、权限、会话；`@tool` + `create_sdk_mcp_server` 做进程内工具；包内自带 Claude Code CLI | MIT（使用受 Anthropic 商业条款约束）/ PyPI 0.2.184（2026-11-18），分类器为 Alpha / 支持：发布流程构建 macOS、Linux、Windows wheels | B 机"智能子 agent"的长期形态，用 hooks 把进度推给 coordinator | 演示：可选（`claude -p` 更省事）/ 长期：用 | [overview](https://code.claude.com/docs/en/agent-sdk/overview)，[subagents](https://code.claude.com/docs/en/agent-sdk/subagents)，[hooks](https://code.claude.com/docs/en/agent-sdk/hooks)，[README](https://github.com/anthropics/claude-agent-sdk-python) |
| Claude Code headless（`claude -p`） | https://code.claude.com/docs/en/headless | 非交互运行：`--output-format json/stream-json`、`--allowedTools`、`--bare`（跳过本机 hooks/MCP/CLAUDE.md 自动发现，官方推荐脚本场景使用）、`--json-schema` 结构化输出 | 随 Claude Code 发布 | B 机 daemon 以子进程方式调用，逐行转发 stream-json 事件 | 演示：**用** / 长期：可被 SDK 替代 | [headless](https://code.claude.com/docs/en/headless) |
| OpenAI Agents SDK（只作对照） | https://github.com/openai/openai-agents-python | 多 agent 工作流：Agents、handoffs、agents-as-tools、guardrails、sessions、tracing、realtime/voice agents、sandbox agents；声称支持 100+ 种 LLM | MIT / PyPI 0.25.0（2026-11-18）/ `UnixLocalSandboxClient` 只支持 macOS/Linux，Windows 要用 Docker 或托管 sandbox | 无（我们的语音层是 Agora，设备侧是 Claude Code） | 演示：跳过 / 长期：跳过 | [README](https://github.com/openai/openai-agents-python) |

### D. 长期记忆（用户可查看/编辑/删除）

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议（11/28 演示 / 长期） | 来源 |
|---|---|---|---|---|---|---|
| SQL 基线：SQLite + FTS5 | https://www.sqlite.org/fts5.html | FTS5 是 SQLite 的全文检索虚拟表模块。自建 `memories` 表（id/user_id/content/category/source/created_at/updated_at/deleted_at），配 CRUD REST 和一个管理页 | FTS5 从 3.9.0（2015-10-14）起进入 amalgamation；Python `sqlite3` 是否编入 FTS5 取决于构建，可用 `PRAGMA compile_options;` 检查 | 演示阶段的记忆库，管理 App 直接读写 | 演示：**用** / 长期：作为真相源保留 | [FTS5](https://www.sqlite.org/fts5.html) |
| mem0（OSS 库 / 自托管服务 / 云平台） | https://github.com/mem0ai/mem0 | `add()` 默认用 LLM 抽取事实并消解冲突（`infer=False` 时原样存）；OSS Python 有 `search/get_all/get/update/delete/delete_all`；自托管服务（docker compose）带 dashboard，有 Memories 浏览检索页和 Entities 级联删除；平台版独占批量更新、webhooks 等功能 | Apache-2.0 / PyPI `mem0ai` 2.2.1（2026-09-25），仓库 2026-11-18 推送 / 库默认用 OpenAI `gpt-5-mini` + `text-embedding-3-small`，Qdrant 存 `/tmp/qdrant`，SQLite 历史存 `~/.mem0/history.db`；自托管用 Postgres/pgvector | 第二阶段的抽取和语义检索层，写回我们自己的表 | 演示：不用 / 长期：候选（首选） | [README](https://github.com/mem0ai/mem0)，[python quickstart](https://docs.mem0.ai/open-source/python-quickstart)，[llms.txt](https://docs.mem0.ai/llms.txt)，[update](https://docs.mem0.ai/core-concepts/memory-operations/update)，[add](https://docs.mem0.ai/core-concepts/memory-operations/add)，[self-host setup](https://docs.mem0.ai/open-source/setup) |
| Letta（原 MemGPT） | https://github.com/letta-ai/letta | 旧的 V1 Python API 服务器**已退役**（代码在 `archive` 分支）；现行源码是 letta-code：npm 安装或 `uv tool install letta`，记忆存在 git 版本化的 MemFS 中，用 `/memory` 查看、`/remember` 教，默认用 Letta Cloud | Apache-2.0 / letta 仓库 2026-10-18 推送；PyPI `letta` 0.34.12（2026-10-12）/ wheels 支持 Windows x64，原生 Windows 默认关闭自动 dreaming | 不适合作为我们服务端的记忆库（它是完整的 agent 运行时） | 演示：跳过 / 长期：参考（MemFS 的 git 版本化思路） | [letta README](https://github.com/letta-ai/letta)，[letta-code README](https://github.com/letta-ai/letta-code)，[memory](https://docs.letta.com/letta-code/memory) |
| Graphiti（Zep） | https://github.com/getzep/graphiti | 时序知识图谱：事实有有效期，信息变化时旧事实被标为失效而不是删除；混合检索；附带参考 MCP/REST 服务器（**不鉴权**） | Apache-2.0 / PyPI `graphiti-core` 0.31.2（2026-10-20），仓库 2026-11-17 推送 / 需要 Neo4j 5.26、FalkorDB 1.1.2 或 Neptune | 将来要问"某事以前是什么、何时变了"时再考虑 | 演示：跳过 / 长期：可选 | [README](https://github.com/getzep/graphiti) |
| Omi 记忆 | https://docs.omi.me/doc/how-omi-works/conversations-and-memories | 记忆是从对话中抽出的短事实，分为 `interesting`/`system`/`manual` 三类，每条可溯源到原对话；"You can review, edit, and delete memories in the app"；API 提供 `GET/POST /v1/dev/user/memories`、`PATCH`/`DELETE /v1/dev/user/memories/{memory_id}`，批量创建每次最多 25 条 | MIT（代码）；API 指向 Omi Cloud | 记忆 App 的 UX 和字段设计参考（分类、来源、可见性） | 演示：参考 / 长期：参考 | [记忆模型](https://docs.omi.me/doc/how-omi-works/conversations-and-memories)，[update](https://docs.omi.me/api-reference/endpoint/memories/update)，[delete](https://docs.omi.me/api-reference/endpoint/memories/delete)，[API overview](https://docs.omi.me/doc/developer/api/overview) |
| OpenClaw 记忆 | https://docs.openclaw.ai/concepts/memory | 记忆就是工作区里的纯 Markdown 文件：`USER.md`（偏好）、`MEMORY.md`（长期事实）、`memory/YYYY-MM-DD.md`（每日笔记）、`DREAMS.md`；默认后端是 SQLite（关键词、向量、混合检索）；有溯源和删除机制，CLI `openclaw memory forget` | MIT | "人可直接编辑的记忆文件 + 索引"的设计参考 | 演示：参考 / 长期：参考 | [memory](https://docs.openclaw.ai/concepts/memory)，[llms.txt](https://docs.openclaw.ai/llms.txt) |

### E. 后期物理扩展（只记"agent 能否通过工具调用"）

| 名称 | 链接 | 做什么 | 状态（许可证 / 最近活动 / Windows 支持） | 在本项目怎么用 | 建议（11/28 演示 / 长期） | 来源 |
|---|---|---|---|---|---|---|
| Home Assistant MCP Server 集成 | https://www.home-assistant.io/integrations/mcp_server/ | HA 自身作为 MCP server（2025.2 引入），端点 `/api/mcp`，分工具集（如 `/api/mcp/assist`）；OAuth 2.0 + PKCE；工具集"Device control"只能控制已暴露给 Assist 的实体；不支持 sampling 和 notifications | core 为 Apache-2.0，2026-11-18 推送 | coordinator 作为 MCP 客户端控制家居，或把 HA 的 MCP 地址直接配给 Agora | 演示：跳过 / 长期：用 | [mcp_server](https://www.home-assistant.io/integrations/mcp_server/) |
| Home Assistant LLM API | https://contributors.home-assistant.io/core/internals/llm-api/ | `llm.API` 是工具加提示词的组合；Assist API 把 intent 作为工具；集成可以通过 `llm.py` 加工具或注册自定义 API；每个注册的 API 也会通过 MCP 提供 | 同上 | 长期可以把我们的设备能力注册进 HA | 演示：跳过 / 长期：参考 | [llm-api](https://contributors.home-assistant.io/core/internals/llm-api/) |
| HASS.Agent | https://github.com/hass-agent/HASS.Agent | Windows 伴侣程序（.NET 8）：通过 MQTT 把 PC 的命令和传感器接入 HA，支持可交互通知，提供不登录也能运行的 Satellite Service | MIT / 2026-11-16 推送 / **仅 Windows** | 长期"经 HA 控制 Windows 笔记本"的现成通路 | 演示：跳过 / 长期：可选 | [README](https://github.com/hass-agent/HASS.Agent) |
| ROS 2 Nav2（Simple Commander API） | https://docs.nav2.org/rolling/configuration_and_development/simple_commander_api/simple_commander_api/ | "navigation as a library" 的 Python3 接口：`goToPose`（非阻塞）、`goThroughPoses`、`followWaypoints`、`isTaskComplete`、`getFeedback`、`cancelTask`、`getResult`；本身就是"下发、轮询、拿结果"模型 | GitHub API 显示许可证 NOASSERTION；2026-11-18 推送 | 机器人节点的工具可以包一层 Simple Commander | 演示：跳过 / 长期：用 | [simple commander](https://docs.nav2.org/rolling/configuration_and_development/simple_commander_api/simple_commander_api/) |
| huggingface/lerobot | https://github.com/huggingface/lerobot | 统一的 `Robot` 接口（`connect`/`get_observation`/`send_action`），支持 SO101、LeKiwi、Unitree G1 等；还有数据集和策略训练 | Apache-2.0 / PyPI 0.7.0（2026-11-05），要求 Python ≥3.12，分类器 Alpha | 机械臂节点 | 演示：跳过 / 长期：可选 | [README](https://github.com/huggingface/lerobot) |
| PX4 SITL + Gazebo | https://docs.px4.io/main/en/sim_gazebo_gz/ | 用 `make px4_sitl gz_x500` 起仿真；offboard API 走 UDP 14540（多机时 14540–14549），地面站走 14550 | BSD-3-Clause / 2026-11-18 推送 / 文档列出 Ubuntu 22.04、24.04；所读页面未提 Windows/WSL2 | 无人机仿真节点 | 演示：跳过 / 长期：用 | [gazebo](https://docs.px4.io/main/en/sim_gazebo_gz/)，[simulation](https://docs.px4.io/main/en/simulation/) |
| MAVSDK-Python | https://github.com/mavlink/MAVSDK-Python | asyncio 风格的 gRPC 封装，自带 `mavsdk_server`；示例 `System().connect(system_address="udpin://0.0.0.0:14540")` | BSD-3-Clause / 2026-10-15 推送；PyPI `mavsdk-grpc` 4.0.5，`mavsdk` 4.2.1 / 有 Windows wheels | 无人机节点的工具实现 | 演示：跳过 / 长期：用 | [README](https://github.com/mavlink/MAVSDK-Python)，[PyPI mavsdk-grpc](https://pypi.org/project/mavsdk-grpc/) |

---

## 关键事实

### 1. 协议（问题 1）

#### 1.1 MCP 当前规范（2026-07-28）对我们的影响

- **规范已无状态化**：协议元数据随每个请求放在 `_meta` 里；服务端功能是 Resources、Prompts、Tools；客户端功能只剩 Elicitation；Tasks、MCP Apps、Skills 都是 opt-in 扩展，通过 `server/discover` 协商。（[spec](https://modelcontextprotocol.io/specification/latest)）
- **Streamable HTTP 发生了破坏性变化**：
  - 去掉了 GET 流端点和协议级会话（`Mcp-Session-Id`）。
  - 每条消息单独 POST 到同一个端点，响应是 JSON，或者是"仅属于本请求"的 SSE 流（可以先发 `notifications/progress`，再发最终结果）。
  - 服务端不能再主动发请求，elicitation 和 sampling 改用 MRTR，即嵌在结果里的 `InputRequiredResult`。
  - 长期通知改为 `subscriptions/listen`；不支持 `Last-Event-ID` 续传。
  - 每个 POST 必须带 `MCP-Protocol-Version`、`Mcp-Method` 头，`tools/call` 还要带 `Mcp-Name`。
  - 服务端必须校验 `Origin`。
  - 2025-03-26 到 2025-11-25 这几版用的是带会话、GET 流的老形态。

  （[streamable-http](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)，[transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)）
- **鉴权是可选的**：HTTP 传输下，MCP server 是 OAuth 2.1 资源服务器，必须提供 RFC 9728 Protected Resource Metadata，令牌放在 `Authorization: Bearer`，不能放在 query；stdio 传输从环境变量取凭据。（[authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)）
- **Tasks 扩展的现状**：服务端可以为某个请求返回 `CreateTaskResult`，客户端轮询 `tasks/get`，可选订阅 `notifications/tasks`。但官方 Python SDK v2 写明"2026-07-28 moves tasks ... into an official extension (SEP-2663), which this SDK does not implement yet"。（[tasks](https://modelcontextprotocol.io/extensions/tasks/overview)，[whats-new](https://py.sdk.modelcontextprotocol.io/whats-new/)）

#### 1.2 官方 Python SDK（`mcp` v2）落地要点

- `from mcp.server import MCPServer`。v1 里的 `from mcp.server.fastmcp import FastMCP` 已移除（不是弃用），`mcp.server.fastmcp.*` 全部改为 `mcp.server.mcpserver.*`。（[whats-new](https://py.sdk.modelcontextprotocol.io/whats-new/)）
- 挂进 FastAPI 或 Starlette 的方法：`app = mcp.streamable_http_app()`，默认端点是 `/mcp`。
  - 宿主 app 的 lifespan 里必须 `async with mcp.session_manager.run():`，否则首个请求会报 `RuntimeError: Task group is not initialized`。
  - `Mount("/")` 要放在自己的路由**之后**。

  （[asgi](https://py.sdk.modelcontextprotocol.io/run/asgi/)）
- **同一个端点服务新旧两代客户端**："the `streamable_http_app()` you already deploy serves both"。SDK 按 `MCP-Protocol-Version` 头分流；旧客户端会拿到进程内的 `Mcp-Session-Id` 会话。
  - 会话存在进程内 dict 里，多 worker 部署时需要粘性路由。
  - `stateless_http=True` 只作用于旧协议这一路，代价是旧客户端没有服务端→客户端通道：`ctx.elicit()` 会抛 `NoBackChannelError`，通知会被丢弃。
  - 文档原话："If your tools never call back into the client, `stateless_http=True` is free and you should take it"。

  （[legacy-clients](https://py.sdk.modelcontextprotocol.io/run/legacy-clients/)）
- 进度：`await ctx.report_progress(done, total=..., message=...)`，客户端调用时传 `progress_callback=` 才会收到。（[progress](https://py.sdk.modelcontextprotocol.io/handlers/progress/)）
- 鉴权：实现 `TokenVerifier.verify_token`，配合 `AuthSettings(issuer_url=..., resource_server_url=..., required_scopes=[...])`，SDK 会自动提供 RFC 9728 元数据。（[authorization](https://py.sdk.modelcontextprotocol.io/run/authorization/)）

#### 1.3 A2A v1.0 要点

- 定位：A2A 是 Google 贡献给 Linux Foundation 的开源项目，用于"opaque agentic applications"之间的通信。附录 B 写明 A2A 与 MCP 互补：A2A 负责 agent 之间的委派和协作，被委派的 agent 内部再用 MCP 调工具。（[README](https://github.com/a2aproject/A2A)，[spec 附录 B](https://a2a-protocol.org/latest/specification/)）
- 发现：Agent Card 放在 `GET /.well-known/agent-card.json`，里面声明能力、技能、端点和安全方案（API key、HTTP、OAuth2、OIDC、mTLS）。
- 操作：SendMessage、SendStreamingMessage、GetTask、ListTasks、CancelTask、SubscribeToTask、push 通知配置的增删查、GetExtendedAgentCard。
  - SendMessage **默认阻塞**，直到任务进入终态或中断态；`returnImmediately: true` 时立即返回。
  - 流式事件有 `TaskStatusUpdateEvent` 和 `TaskArtifactUpdateEvent`。
  - push 通知是服务端向**客户端的 webhook** 发 HTTP POST。
- 绑定：JSON-RPC、gRPC、HTTP+JSON/REST，另有"Custom Binding Guidelines"（第 12 节），其中提到可以用 WebSockets 实现流。

  （[spec](https://a2a-protocol.org/latest/specification/)）
- Python SDK `a2a-sdk` 1.3.1："implements the A2A Protocol Specification `1.0`, with compatibility mode for `0.3`"。（[a2a-python](https://github.com/a2aproject/a2a-python)）

#### 1.4 结论：哪种协议适合"coordinator 把子任务交给设备 agent，并拿回进度和结果"

- **语义上，A2A 最贴合**：它有任务生命周期（含 INPUT_REQUIRED 等人工介入状态）、流式状态和产物、push 通知。MCP 是"宿主 LLM 调工具"的协议；它的长任务机制（Tasks）是扩展，而且 Python SDK 还没实现。（来源同 1.1、1.3）
- **但拓扑不匹配**：两种协议的标准 HTTP 绑定都要求"被委派方（A2A server / MCP server）可以被调用方访问到"。而我们已经定了"设备在 NAT 后、只主动外连 WSS"。
  - A2A 的 push 是服务端→客户端 webhook，同样要求反向可达。
  - 要走 WebSocket，只能用 A2A 的自定义绑定，而那就失去了现成 SDK 的互操作性。（[spec](https://a2a-protocol.org/latest/specification/) §12）
- **因此建议**：
  - coordinator 对 LLM 宿主一侧（Agora、Claude Code、ESP-Claw）用 **MCP**。
  - coordinator 对设备一侧用**自有 JSON-over-WSS**，消息结构照 A2A Task 设计：`task_id`、`context_id`、`state`（submitted/working/input_required/completed/failed/canceled/rejected）、`status.message`、`artifacts[]`。
  - 将来 coordinator 本身是公网可达的，可以作为 **A2A server** 接受第三方 agent 委派，这个方向没有 NAT 问题。
  - （以上为基于一手事实的设计推论。）
- **Agora 一侧的硬约束**：
  - 自定义工具"makes one synchronous request"，并且不支持"Asynchronous tools, callbacks, polling"，超时 1000–100000 ms（[custom-tools](https://github.com/AgoraIO/docs-portal/blob/main/content/docs/en/ai/build/tools/custom-tools.mdx)）。
  - MCP 工具只有 `timeout_ms`，超时后"the agent stops waiting for a response and continues"（[mcp-tools](https://docs.agora.io/en/ai/build/tools/mcp-tools)）。
  - 所以 `build_webpage` 这类工具必须立即返回 `task_id`。进度和完成用 `POST https://api.agora.io/api/conversational-ai-agent/v2/projects/{appid}/agents/{agentId}/speak` 播报：`text` ≤512 字节，`priority` 选 `APPEND`，避免打断用户；MLLM 模式下不可用。（[speak](https://docs.agora.io/en/api-reference/api-ref/conversational-ai/speak)）

#### 1.5 把 coordinator 暴露成 MCP server，Agora、Claude Code、ESP-Mosaico 能否共用同一套工具？

结论：**Agora 和 Claude Code 可以，ESP-Claw 有条件可以（鉴权有缺口）**。

| 调用方 | 能否调用同一 MCP 端点 | 关键事实 | 来源 |
|---|---|---|---|
| Agora ConvoAI | 能 | `llm.mcp_servers[]`：`name`（≤48 字符，只能字母和数字）、`endpoint`、`transport`（"Currently only `streamable_http` is supported"）、`headers`（可放 `Authorization`）、`allowed_tools`、`timeout_ms`；必须开 `advanced_features.enable_tools`，否则"the LLM never calls any tools, with no error"；`allowed_tools` 写错名字不会报错，只会挂起；所有工具（自定义、MCP、内置）共享一个命名空间，最多 32 个；MLLM 用 `mllm.mcp_servers` | [mcp-tools](https://docs.agora.io/en/ai/build/tools/mcp-tools)，[custom-tools](https://github.com/AgoraIO/docs-portal/blob/main/content/docs/en/ai/build/tools/custom-tools.mdx) |
| Claude Code（A/B 机） | 能 | `claude mcp add --transport http <name> <url> --header "Authorization: Bearer <token>"`；HTTP 是推荐的远程传输，SSE 已弃用；`MCP_TOOL_TIMEOUT` 控制工具超时；HTTP 空闲超时默认 5 分钟 | [Claude Code MCP](https://code.claude.com/docs/en/mcp) |
| ESP-Claw / esp-mosaico-claw | 有条件 | esp-mosaico-claw README："Integrates the ESP-Claw Agent Runtime with ... MCP client/server support"。客户端能力 `mcp_call_tool` 的参数是 `server_url`（必填）、`endpoint`、`tool_name`、`arguments`。底层依赖 `espressif/mcp-c-sdk ^2.0.0` 的 HTTP 客户端传输；该 SDK 默认目标版本是 MCP 2025-11-25（握手时代），会带 `Accept: application/json, text/event-stream` 和 `MCP-Protocol-Version`，正好由我们的 Python SDK 服务端的旧协议路径接住。**但** `cap_mcp_client_core.c` 里的 `esp_http_client_config_t` 只设置了 `url`、`timeout_ms=20000`、`buffer_size=4096`、`keep_alive_enable`，没有自定义头，因此**原样无法发送 Bearer 令牌**；ESP-Claw 文档也没写客户端鉴权和 TLS。它的 MCP **server** 用 SSE 传输加 mDNS，面向局域网 | [esp-mosaico-claw](https://github.com/esp-mosaico/esp-mosaico-claw)，[cap-mcp](https://esp-claw.com/en/reference-cap/cap-mcp/)，[idf_component.yml](https://github.com/espressif/esp-claw/blob/master/components/claw_capabilities/cap_mcp_client/idf_component.yml)，[client core 源码](https://github.com/espressif/esp-claw/blob/master/components/claw_capabilities/cap_mcp_client/src/cap_mcp_client_core.c)，[mcp-c-sdk](https://components.espressif.com/components/espressif/mcp-c-sdk/versions/2.0.0/readme) |

实施要点（由上述事实推出）：

- 用 `stateless_http=True`，工具里不用 `ctx.elicit()`。
- 工具总数控制在 32 个以内（Agora 上限）。
- 长任务一律立即返回。
- 给 ESP 开一个单独的低权限端点（例如只读工具，加 IP 限制或路径令牌），或者修改固件给 `esp_http_client` 加头；注意 MCP 规范禁止把令牌放进 query string。

### 2. OpenClaw：node 如何配对、暴露哪些命令（问题 2）

- **是什么**：一个开源个人 AI 助手，跑在你自己的电脑上，并接入 Discord、Slack、Telegram、WhatsApp 等 20 多个渠道，另有 macOS、iOS、Android、Windows、Linux 原生 App。模型和 agent harness（Claude、Codex、本地模型）都是插件。由 OpenClaw Foundation（501(c)(3)）维护，MIT 许可，没有付费层。（[README](https://github.com/openclaw/openclaw)）
- **架构**：
  - Gateway 是会话、工具、事件、渠道的本地控制平面。
  - node 是伴侣设备，"doesn't run the gateway service"，以 `role: "node"` 连接 Gateway 的 WebSocket（Apple Watch 例外，用签名 HTTPS 轮询）。

  （[nodes](https://docs.openclaw.ai/nodes)）
- **无头 node**：`openclaw node run --host <gateway-host> --port 18789`，或者用 `--pair "oc-pair://<setup-code>"`；支持 `--tls`、`--tls-fingerprint`。
  - 默认暴露 `system.run` 和 `system.which`，用 `--commands` 收窄。
  - 用途写明"Run commands on remote Linux/Windows boxes"。
  - 执行受 exec approvals 和每个 agent 的 allowlist 约束。
  - node 可以通过 `nodeHost.mcp.servers` 发布 MCP 工具（命令族 `mcp.tools.call.v1`）。
  - 自动提供浏览器代理。

  （[cli/node](https://docs.openclaw.ai/cli/node)）
- **配对分两层**，都存在 Gateway 的 SQLite 设备记录里：
  - **设备配对**（role `node`）控制 WebSocket `connect` 握手，用 `openclaw devices approve` 批准。
  - **能力审批**（`node.pair.*`）控制已连接的 node 可以暴露哪些命令，用 `openclaw nodes pending` / `approve` / `reject` 处理。新增或扩大命令面会生成 pending 请求，这些请求不会过期。
  - `--pair` 首连用一次性、10 分钟有效的 bootstrap token，之后改用持久的设备凭据。
  - 默认 `gateway.nodes.pairing.sshVerify` 开启：如果能通过 SSH 验证设备密钥，就自动批准首次配对。
  - `system.run`、`browser.proxy`、`fs.listDir` 等敏感命令需要 `operator.admin` 权限范围。

  （[gateway/pairing](https://docs.openclaw.ai/gateway/pairing)，[cli/nodes](https://docs.openclaw.ai/cli/nodes)，[cli/node](https://docs.openclaw.ai/cli/node)）
- **调用方式**：
  - 统一经 `node.invoke`，例如 `openclaw nodes invoke --node <id> --command system.which --params '{...}'`。默认 invoke 超时 15 s，支持 `--idempotency-key`。
  - 还有现成子命令：`nodes notify`（`system.notify`）、`location get`、`screen record`、`camera`，以及实验性的 `canvas present/hide/navigate`。
  - shell 执行不走 invoke，而是用 `exec` 工具的 `host=node`。

  （[cli/nodes](https://docs.openclaw.ai/cli/nodes)）
- **和 Claude Code 的关系**：
  - "CLI backends"可以让 agent 回合直接跑在本机 Claude Code 上，`bundleMcp: true` 时通过 loopback MCP 把 Gateway 工具暴露给 Claude Code。（[cli-backends](https://docs.openclaw.ai/gateway/cli-backends)）
  - `openclaw attach` 启动 Claude Code，并授予一个限定到单个会话、临时的 Gateway MCP 权限。（[cli/attach](https://docs.openclaw.ai/cli/attach)）
  - "Cloud Sessions"让编码会话跑在配对设备或云 worker 上，而转录、工作区、凭据都留在 Gateway，模型推理也经 Gateway 代理。（[cloud-sessions](https://docs.openclaw.ai/gateway/cloud-sessions)）
- **Windows**：原生 Windows Hub（WinUI，Win10 20H2+ 和 Win11，安装不需要管理员权限）。它包含 Windows node 模式（屏幕、摄像头、通知、设备状态、talk、受控的 `system.run`），还提供"Local MCP server mode for MCP clients such as Claude Desktop, Claude Code, and Cursor"。（[platforms/windows](https://docs.openclaw.ai/platforms/windows)）
- **安全提示**：README 写明"Tools run on the host for the main session unless you configure sandboxing"，并建议先读安全指南，再把 Gateway 暴露到远端。（[README](https://github.com/openclaw/openclaw)）
- **对本项目**：
  - 它几乎就是"个人 agent + 跨设备节点 + 可编辑记忆 + Claude Code 执行"的现成实现。
  - 但 Gateway 默认跑在用户自己的机器上，和我们的"云端 coordinator + Agora 语音"不是一套。代码量和发布频率也很高（发布日志里 2026 年 11 月已到 v2026.11.5，见 [llms.txt](https://docs.openclaw.ai/llms.txt)）。
  - 10 天内接入风险大，演示阶段只作参考。
  - 长期值得评估两条路：直接以它为底座（Gateway 上云，或者 coordinator 作为它的一个渠道或插件），或者照搬它的两层配对和命令面审批模型。

### 3. UFO³ Galaxy：是什么、成熟度如何（问题 2）

- **是什么**：UFO³ = Galaxy（多设备编排）+ UFO²（设备 agent）。
  - Galaxy 的 ConstellationAgent 把请求分解成 DAG（TaskConstellation），由 TaskOrchestrator 按设备能力异步分派，并根据执行结果动态改写图。
  - 设备间通信是"WebSocket-based Agent Interaction Protocol (AIP)"。
  - 设备 agent 采用"Template-Driven MCP-Empowered"框架。
  - 设备支持 Windows、Linux、Android（"more coming"）；UFO² 仍是 Windows 专用。

  （[README](https://github.com/microsoft/UFO)，[galaxy README](https://github.com/microsoft/UFO/blob/main/galaxy/README.md)）
- **怎么接设备**：
  - 每台设备跑两个进程：`python -m ufo.server.app --port 5000`，以及 `python -m ufo.client.client --ws --ws-server ws://localhost:5000/ws --client-id <id> --platform windows`。
  - 在 `config/galaxy/devices.yaml` 里登记 `device_id`（必须等于 `--client-id`）、`server_url`（必须与服务器 WebSocket URL 完全一致）、`os`、`capabilities`、`auto_connect`、`max_retries`。
  - 用 `python -m galaxy --interactive` 启动。
  - 每个设备 agent 都要有自己的 LLM 配置；示例给的是 Azure OpenAI 和 OpenAI，文档声称也支持 Claude、Gemini、Qwen、DeepSeek。

  （[quick start](https://microsoft.github.io/UFO/getting_started/quick_start_galaxy/)，[galaxy README](https://github.com/microsoft/UFO/blob/main/galaxy/README.md)）
- **成熟度**：
  - README 页脚写"UFO³ is an open-source research project"；2025-11 发布 Galaxy，并附 arXiv:2511.11332 论文。
  - UFO² v2.0.0（2025-04）"Entered Long-Term Support (LTS) status"。
  - Releases 页最新为 v3.0.10、v3.0.9（"Fixed security issues"，含两项 MSRC 修复）、v3.0.8，页面没显示年份。
  - 仓库最后推送 2026-10-30，MIT 许可。
  - DISCLAIMER 说明代码会截取桌面截图发给模型推理。

  （[README](https://github.com/microsoft/UFO)，[releases](https://github.com/microsoft/UFO/releases)，[DISCLAIMER](https://github.com/microsoft/UFO/blob/main/DISCLAIMER.md)）
- **对本项目**：
  - Galaxy 擅长"把一个复杂请求拆给多台设备做 GUI 操作"，但重度依赖截图式 GUI 自动化，每台设备都要配 LLM，定位也是研究项目。
  - 从配置看，是 Galaxy 连向每台设备上的 `server_url`（ws://），这和我们"设备外连云端"的方向相反（快速入门没有明确写连接由谁发起，见"未能核实"）。
  - 结论：演示跳过；长期参考它的 DAG 规划、能力匹配和 AIP 的容错设计，不建议作为底座。

### 4. 编排选型结论（问题 3）

- **演示**：用显式状态机。流程是固定的六步模板，LangGraph 的 checkpoint 和 interrupt 能力用不上，反而要学它"中断后被中断节点从头重跑"等语义（[interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)）。Claude Agent SDK 只放在设备侧。
- **长期**：
  - coordinator 侧：工作流一旦变成"LLM 动态规划 + 多处人工确认 + 需要崩溃恢复"，迁到 LangGraph。它要求 checkpointer 加 `thread_id`；`InMemorySaver` 重启会丢数据，生产环境用 `SqliteSaver` 或 `PostgresSaver`；节点级 pending writes 保证同一 super-step 中已成功的节点不重跑。（[checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)）
  - 设备侧：用 Claude Agent SDK。subagent 只把最终消息返回父级（上下文隔离）；hooks 可以在 `PostToolUse`、`SubagentStop`、`Notification` 时把进度推给 coordinator。（[subagents](https://code.claude.com/docs/en/agent-sdk/subagents)，[hooks](https://code.claude.com/docs/en/agent-sdk/hooks)）
  - 注意：Agent SDK 文档写明，除非事先获批，第三方产品不得为基于 SDK 的 agent 提供 claude.ai 登录或其额度，应使用 API key 鉴权。（[overview](https://code.claude.com/docs/en/agent-sdk/overview)）
- **`claude -p` 的一个细节**：Claude 回合结束后，如果还有后台子 agent 或 Monitor 等工作，进程默认最多空等 10 分钟（`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` 可调）。官方推荐脚本场景加 `--bare`。（[headless](https://code.claude.com/docs/en/headless)）

### 5. 记忆选型结论（问题 4）

- **"用户能在 App 里查看、编辑、删除"支持最好的**：
  - 现成产品里是 **Omi**：官方写明"You can review, edit, and delete memories in the app"，API 有 PATCH/DELETE，记忆有分类和溯源。但它绑定 Omi 的后端和云。
  - 可自托管的组件里是 **mem0 OSS**：完整的按 ID 增删改查，自托管 dashboard 有 Memories 浏览检索页和 Entities 级联删除；dashboard 能否逐条编辑见"未能核实"。
  - **OpenClaw** 用纯 Markdown 文件，人工编辑最直接。
  - **Letta** 的现行版本把记忆放进 git 版本化的 MemFS，主要通过 agent 修改，文档没写直接的删除命令。
  - **Graphiti** 的语义是"失效而不删除"，参考服务器还不鉴权，不适合作为用户可删除的记忆库。

  （来源见表 D）
- **最轻的起步**：SQLite 表加 FTS5，由 coordinator 提供 CRUD API 和一个简单管理页。其次是 mem0 库（`pip install mem0ai`），但它默认依赖 OpenAI 的 LLM 和 embedding，外加本地 Qdrant，且 `add()` 默认经 LLM 抽取（`infer=True`）。（[python quickstart](https://docs.mem0.ai/open-source/python-quickstart)，[add](https://docs.mem0.ai/core-concepts/memory-operations/add)）

---

## 未能核实

- **Agora 的 MCP 客户端实现细节**：用哪个 MCP 协议版本（2025-xx 握手时代还是 2026-07-28），能否处理 SSE 响应和 `notifications/progress`，何时调用 `tools/list`（建会话时还是每轮），MCP 的 `timeout_ms` 取值范围。所读的 mcp-tools 页面都没写。
- **ESP-Claw MCP 客户端**：能否访问 HTTPS 公网端点（源码里的 `esp_http_client_config_t` 没见证书配置，但没有验证实际行为）；`mcp-c-sdk` 客户端能否经别的途径设置自定义头；能否解析 SSE 形式的响应；`mcp_discover` 只发现局域网 mDNS 服务。另外 mcp-c-sdk 页面对目标版本的写法自相矛盾（同时出现 2025-11-25 和 2025-11-05）。
- **MCP 客户端对 Tasks 扩展的支持**：官方 client-matrix 页面抓取到的文本里，Tasks 列对所有客户端都是空白（可能是图标没被抓到）。因此无法确认 Claude Code 或任何客户端支持 Tasks。
- **mem0 自托管 dashboard 能否逐条编辑或删除记忆**：文档只写了 Memories 页"Browse and search"，以及 Entities 页"cascade-delete"。另外 Windows 上默认 Qdrant 路径 `/tmp/qdrant` 的行为未验证。
- **UFO³ Galaxy**：连接由谁发起（Galaxy 主动连设备的 `server_url`，还是相反），快速入门没有明确写；Releases 页面的日期没有年份；有没有官方稳定性或支持级别声明（只看到"open-source research project"）。
- **Open Interpreter 01 的 Windows 支持**：没有查证。从 2024-11-01 起没有推送，这一点已核实。
- **letta-ai/letta-code 的最近提交时间和发布版本**：GitHub 页面没显示，GitHub API 在本次调研中触发了匿名限流。
- **OpenClaw Gateway 能否放在云端，作为我们 coordinator 的一部分来用**：只读到"multiplayer claw"和远程 Gateway 连接的字样，没有查证云部署形态和许可之外的运营约束。
- **MAVSDK-Python 包名**：README 说新包名是 `mavsdk-grpc`、"previously published as `mavsdk`"，但 PyPI 上 `mavsdk` 仍在 2026-11-17 发布了 4.2.1（描述是"Python binding for MAVSDK"），两者的关系没有核实。
- **PX4 SITL + Gazebo 在 Windows/WSL2 上的支持**：所读的 Gazebo 和仿真页面都没提到。
- **Nav2 Simple Commander 与 `NavigateToPose` action 的对应关系**：所读页面没有明确写。
- **a2a-sdk 的 `DefaultRequestHandler`、`InMemoryTaskStore` 等服务端类名**：所读教程页没有出现，只核实到 `AgentExecutor`、`RequestContext`、`EventQueue`、`TaskUpdater`。
- **MCP Python SDK 支持的最低 Python 版本**：README main 分支写 3.11+，PyPI 2.3.0 的元数据是 `>=3.10`，以安装时的实际约束为准。
